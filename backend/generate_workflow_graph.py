"""
Generate workflow graph PNG using LangGraph's built-in visualization.

Usage:
    python backend/generate_workflow_graph.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent.workflow import build_workflow


def main():
    print("Building LangGraph workflow...")
    
    # Build the workflow
    workflow = build_workflow()
    graph = workflow.get_graph()
    
    print("Generating workflow diagram PNG...")
    
    try:
        # Generate PNG using LangGraph's draw_mermaid_png()
        png_data = graph.draw_mermaid_png()
        
        # Save to project root
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "workflow_diagram.png"
        )
        
        with open(output_path, "wb") as f:
            f.write(png_data)
        
        print(f"✅ Workflow diagram saved to: {output_path}")
        print(f"   File size: {len(png_data) / 1024:.1f} KB")
        
        # Also print Mermaid text for README
        print("\n" + "="*60)
        print("Mermaid diagram (for GitHub README):")
        print("="*60)
        mermaid = graph.draw_mermaid()
        print(mermaid)
        print("="*60)
        
        return output_path
        
    except Exception as e:
        print(f"❌ Error generating PNG: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure you have graphviz installed:")
        print("     macOS: brew install graphviz")
        print("     Ubuntu: sudo apt-get install graphviz")
        print("  2. Install Python dependencies:")
        print("     pip install pygraphviz")
        print("  3. Or use the Mermaid text above at https://mermaid.live")
        return None


if __name__ == "__main__":
    main()
