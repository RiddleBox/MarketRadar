# -*- coding: utf-8 -*-
"""
Clean LLM test with proper UTF-8 output
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m1_5_implicit_reasoner.llm_client import create_llm_client
from m2_knowledge_base.industry_graph import IndustryGraph
from llm_config_loader import load_llm_config
import json

def main():
    print("=" * 80)
    print("Real LLM Inference Test")
    print("=" * 80)

    # Load LLM client
    print("\n[Step 1] Loading LLM client...")
    config = load_llm_config()
    llm_client = create_llm_client(config)
    print(f"LLM client type: {type(llm_client).__name__}")

    # Load industry graph
    print("\n[Step 2] Loading industry graph...")
    graph = IndustryGraph.load_from_file('data/industry_graph_full.json')
    print(f"Industry nodes: {len(graph.nodes)}")

    # Initialize inferencer
    print("\n[Step 3] Initializing M1.5 inferencer...")
    inferencer = LLMImplicitSignalInferencer(llm_client, graph)

    # Test case 1: Diplomatic event
    print("\n" + "=" * 80)
    print("Test Case 1: Diplomatic Event - Saudi Crown Prince Visit")
    print("=" * 80)

    test_data_1 = {
        'source': 'Xinhua',
        'category': 'world',
        'title': 'Saudi Crown Prince visits China, signs renewable energy cooperation agreement',
        'content': 'Saudi Crown Prince Mohammed bin Salman visited China on December 15, and both sides signed multiple renewable energy cooperation agreements. According to the agreement, Saudi Arabia plans to invest $50 billion in renewable energy development over the next 5 years, with solar power as a key focus. Chinese companies will participate in the construction of multiple large-scale solar power plants in Saudi Arabia, involving the supply of core equipment such as solar modules and inverters. In addition, both sides will conduct in-depth cooperation in energy storage technology and smart grids. The Saudi Energy Minister stated that the country plans to achieve 50% of electricity from renewable sources by 2030, with solar installed capacity reaching 40GW.',
        'published_at': '2024-12-15'
    }

    print("\n[M1.5 Inference] Starting inference...")
    signals_1 = inferencer.infer(test_data_1)

    if signals_1:
        for signal in signals_1:
            print(f"\nIdentified implicit signal:")
            print(f"  Signal type: {signal.signal_type}")
            print(f"  Industry: {signal.industry}")
            print(f"  Investment opportunity: {signal.investment_opportunity}")
            print(f"  Target symbols: {signal.target_symbols}")
            print(f"  Initial confidence: {signal.confidence:.3f}")

            print(f"\nReasoning chain:")
            for i, link in enumerate(signal.reasoning_chain.causal_links, 1):
                print(f"  {i}. {link.from_event} -> {link.to_event}")
                print(f"     Mechanism: {link.mechanism}")
                print(f"     Confidence: {link.confidence:.3f}")
    else:
        print("No implicit signal identified")

    # Test case 2: Policy event
    print("\n" + "=" * 80)
    print("Test Case 2: Policy Event - Semiconductor Industry Support")
    print("=" * 80)

    test_data_2 = {
        'source': 'NDRC',
        'category': 'policy',
        'title': 'NDRC announces new support policies for integrated circuit industry',
        'content': 'The National Development and Reform Commission announced today a new round of support policies for the integrated circuit industry, including tax incentives, R&D subsidies, and talent introduction. The policy clearly states that integrated circuit design, manufacturing, and packaging companies can enjoy a 10% corporate income tax rate for 10 years. At the same time, the government will establish a 100 billion yuan integrated circuit industry investment fund to support key equipment and material localization. The policy also proposes to introduce 10,000 high-end chip design talents within 3 years and provide housing subsidies and settlement convenience.',
        'published_at': '2024-12-16'
    }

    print("\n[M1.5 Inference] Starting inference...")
    signals_2 = inferencer.infer(test_data_2)

    if signals_2:
        for signal in signals_2:
            print(f"\nIdentified implicit signal:")
            print(f"  Signal type: {signal.signal_type}")
            print(f"  Industry: {signal.industry}")
            print(f"  Investment opportunity: {signal.investment_opportunity}")
            print(f"  Target symbols: {signal.target_symbols}")
            print(f"  Initial confidence: {signal.confidence:.3f}")

            print(f"\nReasoning chain:")
            for i, link in enumerate(signal.reasoning_chain.causal_links, 1):
                print(f"  {i}. {link.from_event} -> {link.to_event}")
                print(f"     Mechanism: {link.mechanism}")
                print(f"     Confidence: {link.confidence:.3f}")
    else:
        print("No implicit signal identified")

    print("\n" + "=" * 80)
    print("Test completed")
    print("=" * 80)

if __name__ == '__main__':
    main()
