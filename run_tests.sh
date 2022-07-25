#!/usr/bin/env bash

# Step 0: Uncompress test_case.tar.gz and cd into it.
rm -rf test_case/
tar -zxvf test_case.tar.gz 
cd test_case/

# Step 1: create genome listing inputs for lsaBGC-Ready.py
listAllGenomesInDirectory.py -i Primary_Genomes/ > Primary_Genomes_Listing.txt
listAllGenomesInDirectory.py -i Additional_Genomes > Additional_Genomes_Listing.txt

# Step 2: create BGC prediction Genbank listing input for lsaBGC-Ready.py (using AntiSMASH)
listAllBGCGenbanksInDirectory.py -i Primary_Genome_AntiSMASH_Results/ -p antiSMASH \
	-f  > Primary_Genome_BGC_Genbanks_Listing.txt

# Step 3: run lsaBGC-Ready.py - with clustering of primary genome BGCs, expansion to 
#         additional genomes, and phylogeny construction set to automatically run.
FILE=../db/database_location_paths.txt
if [ -f "$FILE" ]; then
    lsaBGC-Ready.py -i Primary_Genomes_Listing.txt -d Additional_Genomes_Listing.txt \
   	-l Primary_Genome_BGC_Genbanks_Listing.txt -p antiSMASH -m BGC_Only \
	  -c 40 -t -a -lc -le -o lsaBGC_Ready_Results/
else
    lsaBGC-Ready.py -i Primary_Genomes_Listing.txt -d Additional_Genomes_Listing.txt \
	  -l Primary_Genome_BGC_Genbanks_Listing.txt -p antiSMASH -m BGC_Only \
	  -c 40 -t -lc -le -o lsaBGC_Ready_Results/
fi

# Step 4: run lsaBGC-AutoAnalyze.py - automatically run analytical programs for
#         visualization, evolutionary stats computation and single row per 
#         homolog group/gene tables. Can also perform metagenomic analysis 
#         if requested.
lsaBGC-AutoAnalyze.py -i lsaBGC_Ready_Results/Final_Results/Expanded_Sample_Annotation_Files.txt \
	-g lsaBGC_Ready_Results/Final_Results/Expanded_GCF_Listings/ \
	-m lsaBGC_Ready_Results/Final_Results/Expanded_Orthogroups.tsv \
	-s lsaBGC_Ready_Results/Final_Results/GToTree_output.tre \
	-w lsaBGC_Ready_Results/Final_Results/GToTree_Expected_Similarities.txt \
	-k lsaBGC_Ready_Results/Final_Results/Samples_in_GToTree_Tree.txt \
	-u Genome_to_Species_Mapping.txt -c 40 -o lsaBGC_AutoAnalyze_Results/ \
