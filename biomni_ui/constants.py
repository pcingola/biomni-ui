_SERVER_PORTS: dict[str, int] = {
    "biochemistry_mcp": 8001,
    "bioengineering_mcp": 8002,
    "biophysics_mcp": 8003,
    "cancer_biology_mcp": 8004,
    "cell_biology_mcp": 8005,
    "database_mcp": 8006,
    "genetics_mcp": 8007,
    "genomics_mcp": 8008,
    "immunology_mcp": 8009,
    "literature_mcp": 8010,
    "microbiology_mcp": 8011,
    "molecular_biology_mcp": 8012,
    "pathology_mcp": 8013,
    "pharmacology_mcp": 8014,
    "physiology_mcp": 8015,
    "support_tools_mcp": 8016,
    "synthetic_biology_mcp": 8017,
    "systems_biology_mcp": 8018,
}

TOOL_SELECTOR_PROMPT = """
You are an expert biomedical research assistant. Your task is to select the relevant resources to help answer a user's query.

Below are the available resources. For each category, select items that are directly or indirectly relevant to answering the query.
Be generous in your selection - include resources that might be useful for the task, even if they're not explicitly mentioned in the query.
It's better to include slightly more resources than to miss potentially useful ones.

AVAILABLE TOOLS:
{tools}

AVAILABLE DATA LAKE ITEMS:
{data}

AVAILABLE LIBRARIES:
{libraries}

IMPORTANT GUIDELINES:
1. Be generous but not excessive - aim to include all potentially relevant resources
2. ALWAYS prioritize database tools for general queries - include as many database tools as possible
3. Include all literature search tools
4. For wet lab sequence type of queries, ALWAYS include molecular biology tools
5. For data lake items, include datasets that could provide useful information
6. For libraries, include those that provide functions needed for analysis
7. Don't exclude resources just because they're not explicitly mentioned in the query
8. When in doubt about a database tool or molecular biology tool, include it rather than exclude it
"""

EXECUTOR_PROMPT = """
You are a biomedical problem-solver with access to tools, datasets, and software.
Work step-by-step, but return outputs ONLY as a JSON object that exactly matches the
`ExecutionResult` schema provided below. Do not include prose or markdown.

## Role & behavior
- Think internally. Do not reveal chain-of-thought.
- For each concrete action you take, append one `Step` to the `step` list.
- If you run code or a command via provided tools, capture logs in `stdout` (and `stderr` on failures).
- Keep code itself out of the JSON unless a tool explicitly returns it; summarize effects in `result`.
- Use citations whenever you rely on outside facts and you have a specific source (url, dois..) so the user can verify: per-step in `step[i].cites`. Return None if no specific source is used.

## Tools & resources
- Use the provided tools first when available. If a tool is missing, explain the limitation in the `result`.
- Data lake root: {BIOMNI_DATA_PATH}/data_lake
- Candidate tools (prioritize these):
{TOOLS}

- Candidate datasets (with descriptions):
{DATA}

- Software libraries (with descriptions):
{LIBRARIES}

## STRICT OUTPUT CONTRACT — ExecutionResult ONLY

**CRITICAL: You MUST return ONLY a valid JSON object. No markdown code blocks, no extra text, no comments.**

The response must be a valid JSON object that exactly matches this ExecutionResult schema:

{
  "step": [
    {
      "name": "string (required)",
      "description": "string",
      "resources": [{"name":"...", "reason":"..."}],
      "result": "string",
      "cites": ["https://..."],
      "output_files": ["relative-or-filename.ext"],
      "stderr": "string?"
    },
    {
      "name": "string (required)",
      "description": "string",
      "resources": [{"name":"...", "reason":"..."}],
      "result": "string",
      "cites": ["https://..."],
      "output_files": ["relative-or-filename.ext"],
      "stderr": "string?"
    }
  ],
  "summary": "string",
  "jupyter_notebook": "string?"
}

**CRITICAL FORMATTING REQUIREMENTS:**
- Return the JSON object directly, with no markdown formatting like ```json or ```
- Do not wrap the JSON in any code blocks or additional text
- The response must start with { and end with }
- No extra keys beyond what's shown in the schema above.
- Use null for unknown optionals; [] for empty lists. Don't provide lists inside of the json as strings.
- Include at least one step. Every step must have non-empty name, description, and result
- Do not fabricate stderr/output_files. If nothing ran, set them to null
- Truncate very long logs to ~10000 characters and note the truncation in `stderr`.
- ALWAYS provide a summary with key findings and insights.

## File generation rules
- Do NOT call plt.show() / display(); use a non-interactive backend (e.g., matplotlib.use('Agg')) and save files.
- Filenames: use a short slug for the task + UTC timestamp, e.g. `align-reads-20250101-120102.ext`.
- When you return paths in `output_files` or `jupyter_notebook`, return ABSOLUTE paths.
- Include all relevant files coming from that step in the "output_files" list.

## Notebook generation contract (MANDATORY)
- You MUST generate a Jupyter Notebook that reproduces the analysis.
- Save as: {task_slug}-{utc_ts}.ipynb
- Set `jupyter_notebook` to that exact path in the FINAL JSON (not null).
- Follow the cell structure described earlier (preamble, env, config, one cell per step, summary, references).

"""

AVAILABLE_LIBRARIES = {
    # === PYTHON PACKAGES ===
    # Core Bioinformatics Libraries (Python)
    "biopython": "[Python Package] A set of tools for biological computation including parsers for bioinformatics files, access to online services, and interfaces to common bioinformatics programs.",
    "biom-format": "[Python Package] The Biological Observation Matrix (BIOM) format is designed for representing biological sample by observation contingency tables with associated metadata.",
    "scanpy": "[Python Package] A scalable toolkit for analyzing single-cell gene expression data, specifically designed for large datasets using AnnData.",
    "scikit-bio": "[Python Package] Data structures, algorithms, and educational resources for bioinformatics, including sequence analysis, phylogenetics, and ordination methods.",
    "anndata": "[Python Package] A Python package for handling annotated data matrices in memory and on disk, primarily used for single-cell genomics data.",
    "mudata": "[Python Package] A Python package for multimodal data storage and manipulation, extending AnnData to handle multiple modalities.",
    "pyliftover": "[Python Package] A Python implementation of UCSC liftOver tool for converting genomic coordinates between genome assemblies.",
    "biopandas": "[Python Package] A package that provides pandas DataFrames for working with molecular structures and biological data.",
    "biotite": "[Python Package] A comprehensive library for computational molecular biology, providing tools for sequence analysis, structure analysis, and more.",
    # Genomics & Variant Analysis (Python)
    "gget": "[Python Package] A toolkit for accessing genomic databases and retrieving sequences, annotations, and other genomic data.",
    "lifelines": "[Python Package] A complete survival analysis library for fitting models, plotting, and statistical tests.",
    # "scvi-tools": "[Python Package] A package for probabilistic modeling of single-cell omics data, including deep generative models.",
    "gseapy": "[Python Package] A Python wrapper for Gene Set Enrichment Analysis (GSEA) and visualization.",
    "scrublet": "[Python Package] A tool for detecting doublets in single-cell RNA-seq data.",
    "cellxgene-census": "[Python Package] A tool for accessing and analyzing the CellxGene Census, a collection of single-cell datasets. To download a dataset, use the download_source_h5ad function with the dataset id as the argument (856c1b98-5727-49da-bf0f-151bdb8cb056, no .h5ad extension).",
    "hyperopt": "[Python Package] A Python library for optimizing hyperparameters of machine learning algorithms.",
    "scvelo": "[Python Package] A tool for RNA velocity analysis in single cells using dynamical models.",
    "pysam": "[Python Package] A Python module for reading, manipulating and writing genomic data sets in SAM/BAM/VCF/BCF formats.",
    "pyfaidx": "[Python Package] A Python package for efficient random access to FASTA files.",
    "pyranges": "[Python Package] A Python package for interval manipulation with a pandas-like interface.",
    "pybedtools": "[Python Package] A Python wrapper for Aaron Quinlan's BEDTools programs.",
    # "panhumanpy": "A Python package for hierarchical, cross-tissue cell type annotation of human single-cell RNA-seq data",
    # Structural Biology & Drug Discovery (Python)
    "rdkit": "[Python Package] A collection of cheminformatics and machine learning tools for working with chemical structures and drug discovery.",
    "deeppurpose": "[Python Package] A deep learning library for drug-target interaction prediction and virtual screening.",
    "pyscreener": "[Python Package] A Python package for virtual screening of chemical compounds.",
    "openbabel": "[Python Package] A chemical toolbox designed to speak the many languages of chemical data, supporting file format conversion and molecular modeling.",
    "descriptastorus": "[Python Package] A library for computing molecular descriptors for machine learning applications in drug discovery.",
    # "pymol": "[Python Package] A molecular visualization system for rendering and animating 3D molecular structures.",
    "openmm": "[Python Package] A toolkit for molecular simulation using high-performance GPU computing.",
    "pytdc": "[Python Package] A Python package for Therapeutics Data Commons, providing access to machine learning datasets for drug discovery.",
    # Data Science & Statistical Analysis (Python)
    "pandas": "[Python Package] A fast, powerful, and flexible data analysis and manipulation library for Python.",
    "numpy": "[Python Package] The fundamental package for scientific computing with Python, providing support for arrays, matrices, and mathematical functions.",
    "scipy": "[Python Package] A Python library for scientific and technical computing, including modules for optimization, linear algebra, integration, and statistics.",
    "scikit-learn": "[Python Package] A machine learning library featuring various classification, regression, and clustering algorithms.",
    "matplotlib": "[Python Package] A comprehensive library for creating static, animated, and interactive visualizations in Python.",
    "seaborn": "[Python Package] A statistical data visualization library based on matplotlib with a high-level interface for drawing attractive statistical graphics.",
    "statsmodels": "[Python Package] A Python module for statistical modeling and econometrics, including descriptive statistics and estimation of statistical models.",
    "pymc3": "[Python Package] A Python package for Bayesian statistical modeling and probabilistic machine learning.",
    # "pystan": "[Python Package] A Python interface to Stan, a platform for statistical modeling and high-performance statistical computation.",
    "umap-learn": "[Python Package] Uniform Manifold Approximation and Projection, a dimension reduction technique.",
    "faiss-cpu": "[Python Package] A library for efficient similarity search and clustering of dense vectors.",
    "harmony-pytorch": "[Python Package] A PyTorch implementation of the Harmony algorithm for integrating single-cell data.",
    # General Bioinformatics & Computational Utilities (Python)
    "tiledb": "[Python Package] A powerful engine for storing and analyzing large-scale genomic data.",
    "tiledbsoma": "[Python Package] A library for working with the SOMA (Stack of Matrices) format using TileDB.",
    "h5py": "[Python Package] A Python interface to the HDF5 binary data format, allowing storage of large amounts of numerical data.",
    "tqdm": "[Python Package] A fast, extensible progress bar for loops and CLI applications.",
    "joblib": "[Python Package] A set of tools to provide lightweight pipelining in Python, including transparent disk-caching and parallel computing.",
    "opencv-python": "[Python Package] OpenCV library for computer vision tasks, useful for image analysis in biological contexts.",
    "PyPDF2": "[Python Package] A library for working with PDF files, useful for extracting text from scientific papers.",
    "googlesearch-python": "[Python Package] A library for performing Google searches programmatically.",
    "scikit-image": "[Python Package] A collection of algorithms for image processing in Python.",
    "pymed": "[Python Package] A Python library for accessing PubMed articles.",
    "arxiv": "[Python Package] A Python wrapper for the arXiv API, allowing access to scientific papers.",
    "scholarly": "[Python Package] A module to retrieve author and publication information from Google Scholar.",
    "cryosparc-tools": "[Python Package] Tools for working with cryoSPARC, a platform for cryo-EM data processing.",
    "mageck": "[Python Package] Analysis of CRISPR screen data.",
    "igraph": "[Python Package] Network analysis and visualization.",
    "pyscenic": "[Python Package] Analysis of single-cell RNA-seq data and gene regulatory networks.",
    "cooler": "[Python Package] Storage and analysis of Hi-C data.",
    "trackpy": "[Python Package] Particle tracking in images and video.",
    # "flowcytometrytools": "[Python Package] Analysis and visualization of flow cytometry data.",
    "cellpose": "[Python Package] Cell segmentation in microscopy images.",
    "viennarna": "[Python Package] RNA secondary structure prediction.",
    "PyMassSpec": "[Python Package] Mass spectrometry data analysis.",
    "python-libsbml": "[Python Package] Working with SBML files for computational biology.",
    "cobra": "[Python Package] Constraint-based modeling of metabolic networks.",
    "reportlab": "[Python Package] Creation of PDF documents.",
    "flowkit": "[Python Package] Toolkit for processing flow cytometry data.",
    "hmmlearn": "[Python Package] Hidden Markov model analysis.",
    "msprime": "[Python Package] Simulation of genetic variation.",
    "tskit": "[Python Package] Handling tree sequences and population genetics data.",
    "cyvcf2": "[Python Package] Fast parsing of VCF files.",
    "pykalman": "[Python Package] Kalman filter and smoother implementation.",
    "fanc": "[Python Package] Analysis of chromatin conformation data.",
    "loompy": "A Python implementation of the Loom file format for efficiently storing and working with large omics datasets.",
    "pyBigWig": "A Python library for accessing bigWig and bigBed files for genome browser track data.",
    "pymzml": "A Python module for high-throughput bioinformatics analysis of mass spectrometry data.",
    "optlang": "A Python package for modeling optimization problems symbolically.",
    "FlowIO": "A Python package for reading and writing flow cytometry data files.",
    "FlowUtils": "Utilities for processing and analyzing flow cytometry data.",
    "arboreto": "A Python package for inferring gene regulatory networks from single-cell RNA-seq data.",
    "pdbfixer": "A Python package for fixing problems in PDB files in preparation for molecular simulations.",
    # === R PACKAGES ===
    # Core R Packages for Data Analysis
    "ggplot2": "[R Package] A system for declaratively creating graphics, based on The Grammar of Graphics. Use with subprocess.run(['Rscript', '-e', 'library(ggplot2); ...']).",
    "dplyr": "[R Package] A grammar of data manipulation, providing a consistent set of verbs that help you solve the most common data manipulation challenges. Use with subprocess.",
    "tidyr": "[R Package] A package that helps you create tidy data, where each column is a variable, each row is an observation, and each cell is a single value. Use with subprocess.",
    "readr": "[R Package] A fast and friendly way to read rectangular data like CSV, TSV, and FWF. Use with subprocess.run(['Rscript', '-e', 'library(readr); ...']).",
    "stringr": "[R Package] A cohesive set of functions designed to make working with strings as easy as possible. Use with subprocess calls.",
    "Matrix": "[R Package] A package that provides classes and methods for dense and sparse matrices. Required for Seurat. Use with subprocess calls.",
    # "Rcpp": "[R Package] Seamless R and C++ Integration, allowing R functions to call compiled C++ code. Use with subprocess calls.",
    # "devtools": "[R Package] Tools to make developing R packages easier, including functions to install packages from GitHub. Use with subprocess calls.",
    # "remotes": "[R Package] Install R packages from GitHub, GitLab, Bitbucket, or other remote repositories. Use with subprocess calls.",
    # Bioinformatics R Packages
    "DESeq2": "[R Package] Differential gene expression analysis based on the negative binomial distribution. Use with subprocess.run(['Rscript', '-e', 'library(DESeq2); ...']).",
    "clusterProfiler": "[R Package] A package for statistical analysis and visualization of functional profiles for genes and gene clusters. Use with subprocess calls.",
    # "DADA2": "[R Package] A package for modeling and correcting Illumina-sequenced amplicon errors. Use with subprocess calls.",
    # "xcms": "[R Package] A package for processing and visualization of LC-MS and GC-MS data. Use with subprocess calls.",
    # "FlowCore": "[R Package] Basic infrastructure for flow cytometry data. Use with subprocess calls.",
    "edgeR": "[R Package] Empirical Analysis of Digital Gene Expression Data in R, for differential expression analysis. Use with subprocess calls.",
    "limma": "[R Package] Linear Models for Microarray Data, for differential expression analysis. Use with subprocess calls.",
    "harmony": "[R Package] A method for integrating and analyzing single-cell data across datasets. Use with subprocess calls.",
    "WGCNA": "[R Package] Weighted Correlation Network Analysis for studying biological networks. Use with subprocess calls.",
    # === CLI TOOLS ===
    # Sequence Analysis Tools
    "samtools": "[CLI Tool] A suite of programs for interacting with high-throughput sequencing data. Use with subprocess.run(['samtools', ...]).",
    "bowtie2": "[CLI Tool] An ultrafast and memory-efficient tool for aligning sequencing reads to long reference sequences. Use with subprocess.run(['bowtie2', ...]).",
    "bwa": "[CLI Tool] Burrows-Wheeler Aligner for mapping low-divergent sequences against a large reference genome. Use with subprocess.run(['bwa', ...]).",
    "bedtools": "[CLI Tool] A powerful toolset for genome arithmetic, allowing operations like intersect, merge, count, and complement on genomic features. Use with subprocess.run(['bedtools', ...]).",
    "macs2": "[CLI Tool] Model-based Analysis of ChIP-Seq data, a tool for identifying transcript factor binding sites.",
    # Quality Control and Processing Tools
    "fastqc": "[CLI Tool] A quality control tool for high throughput sequence data. Use with subprocess.run(['fastqc', ...]).",
    "trimmomatic": "[CLI Tool] A flexible read trimming tool for Illumina NGS data. Use with subprocess.run(['trimmomatic', ...]).",
    # Multiple Sequence Alignment and Phylogenetics
    "mafft": "[CLI Tool] A multiple sequence alignment program for unix-like operating systems. Use with subprocess.run(['mafft', ...]).",
    "Homer": "[CLI Tool] Motif discovery and next-gen sequencing analysis.",
    "FastTree": "[CLI Tool] Phylogenetic trees from sequence alignments.",
    "muscle": "[CLI Tool] Multiple sequence alignment tool.",
    # Genetic Analysis Tools
    "plink": "[CLI Tool] A comprehensive toolkit for genome association studies that can perform a range of large-scale analyses in a computationally efficient manner. Use with subprocess.run(['plink', ...]).",
    "plink2": "[CLI Tool] A comprehensive toolkit for genome association studies that can perform a range of large-scale analyses in a computationally efficient manner. Use with subprocess.run(['plink2', ...]).",
    "gcta64": "[CLI Tool] Genome-wide Complex Trait Analysis (GCTA) tool for estimating the proportion of phenotypic variance explained by genome-wide SNPs and analyzing genetic relationships. Use with subprocess.run(['gcta64', ...]).",
    "iqtree2": "[CLI Tool] An efficient phylogenetic software for maximum likelihood analysis with built-in model selection and ultrafast bootstrap. Use with subprocess.run(['iqtree2', ...]).",
    "ADFR": "AutoDock for Receptors suite for molecular docking and virtual screening. ",
    "diamond": "A sequence aligner for protein and translated DNA searches, designed for high performance analysis of big sequence data. ",
    "fcsparser": "A command-line tool for parsing and analyzing flow cytometry standard (FCS) files. ",
    "plannotate": "[CLI Tool] A tool for annotating plasmid sequences with common features. ",
    "vina": "[CLI Tool] An open-source program for molecular docking and virtual screening, known for its speed and accuracy improvements over AutoDock 4.",
    "autosite": "[CLI Tool] A binding site detection tool used to identify potential ligand binding pockets on protein structures for molecular docking.",
}