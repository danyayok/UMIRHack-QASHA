
```cpp
// mock_cpp_agent/send_report.cpp
/*
g++ send_report.cpp -o send_report -lcurl -std=c++17
./send_report http://localhost:8000/api/v1/agents/cpp/report <AGENT_TOKEN>
*/
#include <curl/curl.h>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc < 3) { std::cerr << "Usage: " << argv[0] << " <url> <agent_token>\n"; return 1; }
    std::string url = argv[1], token = argv[2];
    std::string json = R"({
      "agent_name": "mock-cpp-agent",
      "project_id": 1,
      "run_id": "run-123",
      "meta": { "hostname": "mock-runner", "timestamp": "2025-11-07T12:00:00Z", "duration_seconds": 12.5 },
      "payload": { "performance": { "functions": [ { "name": "doWork", "p75_ms": 10.2, "p95_ms": 20.1, "allocations": 5 } ], "max_memory_mb": 128 }, "fuzz": { "runs": 1000, "crashes": [] } }
    })";
    CURL* curl = curl_easy_init(); if (!curl) { std::cerr << "curl init failed\n"; return 1; }
    struct curl_slist* headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    std::string auth = "X-Agent-Token: " + token;
    headers = curl_slist_append(headers, auth.c_str());
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)json.size());
    CURLcode res = curl_easy_perform(curl);
    if (res != CURLE_OK) std::cerr << "curl failed: " << curl_easy_strerror(res) << "\n";
    curl_slist_free_all(headers); curl_easy_cleanup(curl); return 0;
}
