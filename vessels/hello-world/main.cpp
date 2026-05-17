// Hello World Myrmidon — E2E test worker
// Demonstrates the pull-based myrmidon pattern with nats.c JetStream
//
// 1. Connects to NATS
// 2. Ensures homeric-myrmidon stream exists
// 3. Creates durable pull consumer on hi.myrmidon.hello.>
// 4. Pulls one message at a time (MaxAckPending=1), processes, publishes completion

#include <nats.h>
#include <nlohmann/json.hpp>

#include <chrono>
#include <csignal>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>

using json = nlohmann::json;

static volatile bool g_running = true;

void signal_handler(int) { g_running = false; }

std::string now_iso8601() {
    auto now       = std::chrono::system_clock::now();
    auto time_t_now = std::chrono::system_clock::to_time_t(now);
    std::ostringstream ss;
    ss << std::put_time(std::gmtime(&time_t_now), "%FT%TZ");
    return ss.str();
}

// Ensure a stream exists (idempotent — ignores "already exists" errors).
void ensure_stream(jsCtx* js, const char* name, const char** subjects, int subjectsLen) {
    jsStreamConfig cfg;
    jsStreamConfig_Init(&cfg);
    cfg.Name        = name;
    cfg.Subjects    = subjects;
    cfg.SubjectsLen = subjectsLen;

    jsStreamInfo* si = nullptr;
    jsErrCode     jerr{};
    natsStatus    s = js_AddStream(&si, js, &cfg, nullptr, &jerr);
    if (s == NATS_OK) {
        std::cout << "Created stream " << name << "\n";
        jsStreamInfo_Destroy(si);
    } else {
        // Stream may already exist — not fatal.
        std::cout << "Stream " << name << ": " << natsStatus_GetText(s)
                  << " (may already exist)\n";
    }
}

int main(int argc, char* argv[]) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            std::cout << "usage: hello_myrmidon [--help]\n"
                      << "  Connects to NATS (NATS_URL env) and processes hi.myrmidon.hello.> tasks.\n";
            return 0;
        }
    }

    // Disable stdout/stderr buffering for container logging
    std::cout.setf(std::ios::unitbuf);
    std::cerr.setf(std::ios::unitbuf);

    std::signal(SIGINT,  signal_handler);
    std::signal(SIGTERM, signal_handler);

    const char* nats_url_env = std::getenv("NATS_URL");
    std::string nats_url     = nats_url_env ? nats_url_env : "nats://localhost:4222";

    std::cout << "Hello Myrmidon starting, NATS=" << nats_url << "\n";

    // ── Connect to NATS (with retry for container startup ordering) ──────────
    natsConnection* conn = nullptr;
    natsStatus      s    = NATS_ERR;

    for (int attempt = 0; attempt < 30 && s != NATS_OK && g_running; ++attempt) {
        if (attempt > 0) {
            std::cerr << "Connection attempt " << (attempt + 1) << " failed ("
                      << natsStatus_GetText(s) << "), retrying in 5s…\n";
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
        s = natsConnection_ConnectTo(&conn, nats_url.c_str());
    }

    if (s != NATS_OK) {
        std::cerr << "Could not connect to NATS after retries. Exiting.\n";
        return 1;
    }
    std::cout << "Connected to NATS\n";

    // ── JetStream context ────────────────────────────────────────────────────
    jsCtx* js = nullptr;
    s = natsConnection_JetStream(&js, conn, nullptr);
    if (s != NATS_OK) {
        std::cerr << "Failed to get JetStream context: " << natsStatus_GetText(s) << "\n";
        natsConnection_Close(conn);
        natsConnection_Destroy(conn);
        return 1;
    }

    // ── Ensure streams exist ─────────────────────────────────────────────────
    {
        const char* myrmidon_subjects[] = {"hi.myrmidon.>"};
        ensure_stream(js, "homeric-myrmidon", myrmidon_subjects, 1);
    }
    {
        const char* tasks_subjects[] = {"hi.tasks.>"};
        ensure_stream(js, "homeric-tasks", tasks_subjects, 1);
    }
    {
        const char* logs_subjects[] = {"hi.logs.>"};
        ensure_stream(js, "homeric-logs", logs_subjects, 1);
    }

    // ── Create durable pull consumer ─────────────────────────────────────────
    static const char* CONSUMER_NAME = "hello-myrmidon";
    static const char* STREAM_NAME   = "homeric-myrmidon";
    static const char* FILTER_SUBJ   = "hi.myrmidon.hello.>";

    {
        jsConsumerConfig cc;
        jsConsumerConfig_Init(&cc);
        cc.Name           = CONSUMER_NAME;
        cc.Durable        = CONSUMER_NAME;
        cc.FilterSubject  = FILTER_SUBJ;
        cc.AckPolicy      = js_AckExplicit;
        cc.DeliverPolicy  = js_DeliverAll;
        cc.MaxAckPending  = 1;   // Rate limiting: 1 in-flight at a time

        jsConsumerInfo* ci   = nullptr;
        jsErrCode       jerr{};
        s = js_AddConsumer(&ci, js, STREAM_NAME, &cc, nullptr, &jerr);
        if (s == NATS_OK) {
            std::cout << "Created consumer " << CONSUMER_NAME << "\n";
            jsConsumerInfo_Destroy(ci);
        } else {
            // Consumer may already exist — that is fine.
            std::cout << "Consumer " << CONSUMER_NAME << ": " << natsStatus_GetText(s)
                      << " (may already exist)\n";
        }
    }

    // ── Pull subscription ────────────────────────────────────────────────────
    natsSubscription* sub = nullptr;
    {
        jsErrCode jerr{};
        s = js_PullSubscribe(&sub, js, FILTER_SUBJ, CONSUMER_NAME,
                             nullptr, nullptr, &jerr);
    }
    if (s != NATS_OK) {
        std::cerr << "Failed to create pull subscription: " << natsStatus_GetText(s) << "\n";
        jsCtx_Destroy(js);
        natsConnection_Close(conn);
        natsConnection_Destroy(conn);
        return 1;
    }

    std::cout << "Listening for tasks on " << FILTER_SUBJ
              << " (MaxAckPending=1)\n";

    // ── Main processing loop ─────────────────────────────────────────────────
    while (g_running) {
        natsMsgList list{};
        jsErrCode   jerr{};

        // Fetch exactly 1 message, wait up to 5 s.
        s = natsSubscription_Fetch(&list, sub, 1, 5000, &jerr);

        if (s == NATS_TIMEOUT) {
            continue;   // No messages available — keep polling.
        }
        if (s != NATS_OK) {
            std::cerr << "Fetch error: " << natsStatus_GetText(s) << "\n";
            std::this_thread::sleep_for(std::chrono::seconds(1));
            continue;
        }

        for (int i = 0; i < list.Count; ++i) {
            natsMsg*    msg  = list.Msgs[i];
            std::string data(natsMsg_GetData(msg), natsMsg_GetDataLength(msg));

            std::cout << "Received task: " << data << "\n";

            json task;
            try {
                task = json::parse(data);
            } catch (...) {
                std::cerr << "Failed to parse task JSON — nacking\n";
                natsMsg_Nak(msg, nullptr);
                continue;
            }

            std::string task_id = task.value("task_id", "unknown");
            std::string team_id = task.value("team_id", "unknown");
            std::string subject = task.value("subject", "unknown task");

            std::cout << "Processing task " << task_id << ": " << subject << "\n";

            // Simulate work — 1 second.
            std::this_thread::sleep_for(std::chrono::seconds(1));

            // ── Publish completion ────────────────────────────────────────
            std::string completion_subject =
                "hi.tasks." + team_id + "." + task_id + ".completed";

            json completion = {
                {"event", "task.completed"},
                {"data", {
                    {"team_id", team_id},
                    {"task_id", task_id},
                    {"result",  "Hello World! Task processed successfully."},
                    {"status",  "completed"}
                }},
                {"timestamp", now_iso8601()}
            };
            std::string completion_str = completion.dump();

            jsPubAck*  pa    = nullptr;
            jsErrCode  perr{};
            natsStatus ps = js_Publish(&pa, js, completion_subject.c_str(),
                                       completion_str.c_str(),
                                       static_cast<int>(completion_str.size()),
                                       nullptr, &perr);
            if (ps == NATS_OK) {
                std::cout << "Published completion to " << completion_subject << "\n";
                jsPubAck_Destroy(pa);
            } else {
                std::cerr << "Failed to publish completion: " << natsStatus_GetText(ps) << "\n";
            }

            // ── Publish log ───────────────────────────────────────────────
            json log_entry = {
                {"level",     "info"},
                {"service",   "hello-myrmidon"},
                {"message",   "Completed task " + task_id + ": " + subject},
                {"task_id",   task_id},
                {"team_id",   team_id},
                {"timestamp", now_iso8601()}
            };
            std::string log_str = log_entry.dump();

            jsPubAck* lpa = nullptr;
            js_Publish(&lpa, js, "hi.logs.myrmidon.hello",
                       log_str.c_str(), static_cast<int>(log_str.size()),
                       nullptr, nullptr);
            if (lpa) jsPubAck_Destroy(lpa);

            // ── Acknowledge ───────────────────────────────────────────────
            natsMsg_Ack(msg, nullptr);
            std::cout << "Task " << task_id << " completed and acknowledged\n";
        }

        natsMsgList_Destroy(&list);
    }

    // ── Graceful shutdown ────────────────────────────────────────────────────
    std::cout << "\nShutting down hello-myrmidon\n";
    natsSubscription_Destroy(sub);
    jsCtx_Destroy(js);
    natsConnection_Close(conn);
    natsConnection_Destroy(conn);

    return 0;
}
