# Major Updates 
* Apr 17, 2023 - Set AutoExpansion to off by default in lsaBGC-(Euk)-Easy, introduced lsaBGC-ComprehenSeeIve, changed handling off primary genomes being rerun through lsaBGC-AutoExpansion.
* Apr 14, 2023 - Introduced lsaBGC-MIBiGMapper.py, lsaBGC-Euk-Easy.py, visualize_BGC-ome.py, slight updates to plots, added automatic color formatting to spreadsheet, simplified README. 
* Mar 2, 2023 - Added GSeeF analysis to the end of the lsaBGC-Easy workflow and added support for parsing annotations from DeepBGC and GECCO into GSeeF.
* Feb 28, 2023 - Handle similarly named BGCs from different genomic assemblies (due to similar scaffold names) in lsaBGC-Ready.py/lsaBGC-Easy.py + automated ulimit setting updates in lsaBGC-Ready.py similar to what is employed in lsaBGC-Easy.py 
* Feb 5, 2023 - Corrected flag to make prodigal the default and pyrodigal optional unless requested by the user - we are considering formally making pyrodigal the default gene-caller however because there are a number of improvements/corrections pyprodigal offers and it is being actively maintained.
* Jan 16, 2023 - Added more adjustable parameters to lsaBGC-DiscoVary. Expansion uses bitscores to select best homolog group for genes from new genomes while cutoffs still based on E-values to provide more resolution and sensitivity in distinguishing NRPS/PKS homolog groups with recently diverged protocore genes (in alignment with recent v1.31 switch to use more resolute homolog groups).  
* Nov 25, 2022 - Much improved logging and standard output for lsaBGC-Easy (less yelling to the terminal). Recent switch to use hierarchical ortholog groupings found to be non-deterministic (still default - but can use coarser orthogroups via `-mc` argument for `lsaBGC-Easy.py` and `lsaBGC-Ready.py`). `GSeeF.py` made more robust and default is to only print tracks for most common 50 GCFs. 
* Nov 9, 2022 - Switch from using coarse othogrouping to hierarchical ortholog groupings in OrthoFinder analysis. Add option to provide user custom species tree. 
* Nov 6, 2022 - Introduce [`GSeeF.py`](https://github.com/Kalan-Lab/lsaBGC/wiki/17.-GSeeF---Visualizing-GCF-Cluster-Presence-and-Annotation-Along-a-Species-Phylogeny), improve interface of `lsaBGC-Easy.py`, and fix code for synchronizing gene-calling potential differences between BGCs and prodigal on full genomes (introduced in v1.2). 
* Aug 21, 2022 - Parsing of BiG-SCAPE results updated to account for GCFs spanning multiple class categories. All BGC instances in each class the GCF occurs will be conglomerated. Default usage of lsaBGC-Cluster.py is unaffected.
* Aug 16, 2022 - We recently (in version 1.1) had switched from scipy's `median_absolute_deviation` function to `median_abs_deviation` function - to mimic behavior of the original function and how we benchmarked lsaBGC in our manuscript, have set the scale of the function to `normal`. Though we are considering changing the scale to the default of the new function `1.0` in latter versions after further testing.
* Aug 08, 2022 - Added a couple more columns to PopGene report: `single-copy_in_GCF_context`, `max_beta_rd`. Also renamed column `hg median copy count` to a more appropriate label of `hg proportion multi-copy genome-wide` (calculation is the same!). Added `use_core_only` option to codon-alignment comparison methods to more appropriately calculate Beta-RD from recent switch to not regard sites where one sample/protein/gene has an allele but the comparing sample has a gap as a mismatch, but rather such sites are now ignored by default.  
* Aug 04, 2022 - Added some minor code to allow running `lsaBGC-Easy.py` with only an "Additional_Genomes" directory. Command would look something like: `lsaBGC-Easy.py -n "None" -g Genomes_Directory/ -o Results/`
* Aug 01, 2022 - Polished `lsaBGC-Easy.py` and created more streamlined version: see details on its [Wiki page](https://github.com/Kalan-Lab/lsaBGC/wiki/14.-lsaBGC-Easy-Tutorial:-Combining-lsaBGC-with-ncbi-genome-download).
* Jul 28, 2022 - Introduced `lsaBGC-Easy.py` which simplifies usage of the suite. The general suite (besides `lsaBGC-DiscoVary.py`) can also now handle fungal genomes if BGCs are predicted using antiSMASH, but investigating fungal genomes is not currently an option in `lsaBGC-Easy.py`. Additional user interface upgrades + dependencies introduced, as such please reconfigure the conda environment and reinstall if you tried lsaBGC previously! Long-overdue but have a notice on citing the many dependencies now in the main folder of the repo titled: `CITATION_NOTICE`. 
* Jul 12, 2022 - Huge thanks to Martin Larralde for recommendation and advice on how to update GECCO processing to better identify "protocore"-esque genes in BGCs! Also, have now added a simplified sub-section down below with [notes on the PopGene report table](#notes-on-the-popgene-table-report).
* Jul 10, 2022 - Several updates made. Fixed small issues with smooth running of new framework, `lsaBGC-Ready.py`. Removed some dependencies and have added GToTree for creating species phylogeny + estimated sample to sample amino acid expected divergences. New small test dataset now included in this repo for immediate testing + much simplified installation guide. Most major change is that lsaBGC now works with DeepBGC and GECCO predictions! lsaBGC's backend relies on 'proto-core homolog groups' / 'rule-based key domains' determined by AntiSMASH, to get around the absence of such marker genes/domains in DeepBGC and GECCO predictions, domains in the highest 10% of deebgc_scpus or lowest 10% of e-values are treated as "proto-core" and used in `lsaBGC-AutoExpansion.py`/`lsaBGC-DiscoVary.py` as well as highlighted/treated as the "core" in `lsaBGC-PopGene.py` reports.
* Jun 26, 2022 - Added "loose" mode to `lsaBGC-Expansion.py` and option for users to manually define "protocore" homolog groups. Also, "protocore" homolog groups for a GCF now must have "rule-based" marker to exclude MGEs like transposons which insert within protocore regions of BGCs.
* Jun 19, 2022 - Have set MAGUS as the default protein alignment method (highly scalable wrapper of mafft) + updated notes on scalability.
* Jun 18, 2022 - Updated [`lsaBGC-AutoAnalyze.py`](https://github.com/Kalan-Lab/lsaBGC/wiki/13.-The-lsaBGC-AutoAnalyze-Workflow) (automated lsaBGC analysis for each GCF) for better integration into new framework based around `lsaBGC-Ready.py`. 
* Jun 14, 2022 - Added [note on scalability](#user-content-notes-on-scalability), below on this page, and future plans to address them.
* Jun 09, 2022 - Fixed issues with `lsaBGC-Ready.py` & New Tutorial check it out [here](https://github.com/Kalan-Lab/lsaBGC/wiki/03.-Quick-Start-&-In-Depth-Tutorial:-Exploring-BGCs-in-Cutibacterium)!
* Jun 06, 2022 - Major updates to `lsaBGC-Ready.py` - the new recommended program for setting-up to run the lsaBGC suite.
* May 24, 2022 - `lsaBGC-Ready.py` is now available and can take pre-computed antiSMASH BGC predictions, along with optional BiG-SCAPE clustering results, to produce the required inputs for major lsaBGC analytical programs (`lsaBGC-See.py`, `lsaBGC-Refine.py`, `lsaBGC-PopGene.py`, `lsaBGC-DiscoVary.py`). 