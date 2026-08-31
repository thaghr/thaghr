from prometheus_client import Counter, start_http_server

episode_results_total = Counter(
    "thaghr_episode_results_total",
    "Episode outcomes",
    ["result"],  # "pass" | "fail"
)

faults_injected_total = Counter(
    "thaghr_faults_injected_total",
    "Faults injected by type",
    ["fault_type"],
)

repeat_loop_detected_total = Counter(
    "thaghr_repeat_loop_detected_total",
    "Same (tool, args) pair repeated 3+ times within a 6-step window",
    ["tool"],
)

def start_metrics_server(port: int = 9090) -> None:
    start_http_server(port)