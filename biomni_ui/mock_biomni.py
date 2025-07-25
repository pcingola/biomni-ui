import asyncio
import random
import time
from pathlib import Path


class MockA1:
    """Mock implementation of Biomni A1 agent for testing purposes."""
    
    def __init__(self, path: str, llm: str = "mock-model", **kwargs):
        self.path = Path(path)
        self.llm = llm
        self.kwargs = kwargs
        
        # Create mock data directory
        self.path.mkdir(parents=True, exist_ok=True)
        
        print(f"Mock Biomni A1 initialized with path: {path}")
        print(f"Using mock LLM: {llm}")
    
    def go(self, query: str) -> tuple[list[str], str]:
        """Mock implementation of the go method."""
        print(f"Processing query: {query}")
        
        # Simulate processing time
        time.sleep(0.5)
        
        # Generate mock log entries
        log_entries = [
            "Starting biomedical analysis...",
            "Loading relevant datasets...",
            f"Query: {query}",
            "Analyzing biological context...",
            "Searching literature databases...",
            "Processing molecular data...",
            "Generating insights...",
        ]
        
        # Add some randomness to make it more realistic
        if "gene" in query.lower():
            log_entries.extend([
                "Found relevant gene expression data",
                "Analyzing protein interactions",
                "Cross-referencing with pathway databases"
            ])
        elif "protein" in query.lower():
            log_entries.extend([
                "Retrieving protein structure information",
                "Analyzing functional domains",
                "Checking for known variants"
            ])
        elif "drug" in query.lower() or "compound" in query.lower():
            log_entries.extend([
                "Searching compound databases",
                "Analyzing ADMET properties",
                "Checking for drug interactions"
            ])
        
        # Generate final result
        final_result = self._generate_mock_result(query)
        
        return log_entries, final_result
    
    
    def _generate_mock_result(self, query: str) -> str:
        """Generate a mock result based on the query."""
        results = [
            f"## Analysis Results for: {query}",
            "",
            "### Summary",
            "Based on the biomedical analysis, here are the key findings:",
            "",
            "1. **Data Sources**: Analyzed multiple databases including PubMed, UniProt, and KEGG",
            "2. **Methodology**: Applied machine learning algorithms for pattern recognition",
            "3. **Statistical Analysis**: Performed significance testing with p < 0.05",
            "",
            "### Key Findings",
        ]
        
        if "gene" in query.lower():
            results.extend([
                "- Identified 15 relevant genes with significant expression changes",
                "- Found 3 key regulatory pathways involved",
                "- Discovered potential therapeutic targets",
                "",
                "### Recommendations",
                "- Further validation through wet lab experiments recommended",
                "- Consider pathway enrichment analysis",
                "- Investigate protein-protein interactions"
            ])
        elif "protein" in query.lower():
            results.extend([
                "- Analyzed protein structure and function",
                "- Identified 5 functional domains",
                "- Found 2 potential binding sites",
                "",
                "### Recommendations",
                "- Structural modeling recommended",
                "- Consider molecular dynamics simulations",
                "- Investigate allosteric regulation"
            ])
        elif "drug" in query.lower() or "compound" in query.lower():
            results.extend([
                "- Evaluated ADMET properties",
                "- Assessed drug-drug interactions",
                "- Analyzed pharmacokinetic parameters",
                "",
                "### Recommendations",
                "- Clinical trial design considerations",
                "- Dosage optimization studies needed",
                "- Monitor for potential side effects"
            ])
        else:
            results.extend([
                "- Comprehensive literature review completed",
                "- Identified relevant biological mechanisms",
                "- Suggested experimental approaches",
                "",
                "### Recommendations",
                "- Design targeted experiments",
                "- Consider multi-omics approach",
                "- Validate findings in model systems"
            ])
        
        results.extend([
            "",
            "### Generated Files",
            "- analysis_results.txt: Detailed analysis report",
            "- mock_data.csv: Sample data for further analysis",
            "",
            "**Note**: This is a mock response for testing purposes."
        ])
        
        return "\n".join(results)