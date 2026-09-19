from agent_backend.foundation.llm import build_llm_client_registry_from_env
from agent_backend.orchestration.data_analysis.graph import build_data_analysis_graph


def main() -> None:
    llm_registry = build_llm_client_registry_from_env()
    graph = build_data_analysis_graph(model_client=llm_registry.get_default())
    print(f"worker bootstrapped graph={graph}")


if __name__ == "__main__":
    main()

