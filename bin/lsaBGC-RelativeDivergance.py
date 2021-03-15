# !/usr/bin/env python

### Program: lsaBGC-RelativeDivergance.py
### Author: Rauf Salamzade
### Kalan Lab
### UW Madison, Department of Medical Microbiology and Immunology

import os
import sys
from time import sleep
import argparse
from lsaBGC import lsaBGC

def create_parser():
    """ Parse arguments """
    parser = argparse.ArgumentParser(description="""
	Program: lsaBGC-RelativeDivergance.py
	Author: Rauf Salamzade
	Affiliation: Kalan Lab, UW Madison, Department of Medical Microbiology and Immunology

	This program will calculate Beta-RD, the ratio of the estimated ANI between orthologous BGCs from two samples to the
	estimated genome-wide ANI, for all pairs of samples featuring a BGC belonging to a focal GCF of interest.
	""", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-g', '--gcf_listing', help='BGC specifications file. Tab delimited: 1st column contains path to AntiSMASH BGC Genbank and 2nd column contains sample name.', required=True)
    parser.add_argument('-i', '--assembly_listing', help="Sequencing data specifications file. Tab delimited: 1st column contains metagenomic sample name, whereas 2nd and 3rd columns contain full paths to forward and reverse reads, respectively.", required=True)
    parser.add_argument('-c', '--cores', type=int, help="The number of cores to use.", required=False, default=1)

    args = parser.parse_args()

    return args

def lsaBGC_RelativeDivergance():
    """
    Void function which runs primary workflow for program.
    """

    """
    PARSE REQUIRED INPUTS
    """
    myargs = create_parser()

    gcf_listing_file = os.path.abspath(myargs.gcf_listing)
    paired_end_sequencing_file = os.path.abspath(myargs.paired_end_sequencing)
    orthofinder_matrix_file = os.path.abspath(myargs.orthofinder_matrix)
    codon_alignments_file = os.path.abspath(myargs.codon_alignments)
    outdir = os.path.abspath(myargs.output_directory) + '/'

    ### vet input files quickly
    try:
        assert (os.path.isfile(orthofinder_matrix_file))
        assert (os.path.isfile(gcf_listing_file))
        assert (os.path.isfile(paired_end_sequencing_file))
    except:
        raise RuntimeError('One or more of the input files provided, does not exist. Exiting now ...')

    if os.path.isdir(outdir):
        sys.stderr.write("Output directory exists. Overwriting in 5 seconds ...\n ")
        sleep(5)
    else:
        os.system('mkdir %s' % outdir)

    """
    PARSE OPTIONAL INPUTS
    """

    cores = myargs.cores

    """
    START WORKFLOW
    """

    # create logging object
    log_file = outdir + 'Progress.log'
    logObject = lsaBGC.createLoggerObject(log_file)

    # Step 0: Log input arguments and update reference and query FASTA files.
    logObject.info("Saving parameters for future provedance.")
    parameters_file = outdir + 'Parameter_Inputs.txt'
    parameter_values = [gcf_listing_file, orthofinder_matrix_file, paired_end_sequencing_file, outdir, cores]
    parameter_names = ["GCF Listing File", "OrthoFinder Orthogroups.csv File", "Paired-Sequencing Listing File",
                       "Output Directory", "Cores"]
    lsaBGC.logParametersToFile(parameters_file, parameter_names, parameter_values)
    logObject.info("Done saving parameters!")

    # Step 1: Process GCF listings file
    logObject.info("Processing BGC Genbanks from GCF listing file.")
    bgc_gbk, bgc_genes, comp_gene_info, all_genes, bgc_sample, sample_bgcs = lsaBGC.readInBGCGenbanksPerGCF(gcf_listing_file, logObject)
    logObject.info("Successfully parsed BGC Genbanks and associated with unique IDs.")

    # Step 2: Parse OrthoFinder Homolog vs Sample Matrix and associate each homolog group with a color
    logObject.info("Starting to parse OrthoFinder homolog vs sample information.")
    gene_to_cog, cog_genes, cog_prop_multicopy = lsaBGC.parseOrthoFinderMatrix(orthofinder_matrix_file, all_genes, calc_prop_multicopy=True)
    logObject.info("Successfully parsed homolog matrix.")

    # Step 3: Create database of genes with surrounding flanks and, independently, cluster them into allele groups / haplotypes.
    logObject.info("Extracting and clustering GCF genes with their flanks.")
    #bowtie2_reference, instances_to_haplotypes = lsaBGC.extractGeneWithFlanksAndCluster(bgc_genes, comp_gene_info, gene_to_cog, outdir, logObject)
    logObject.info("Successfully extracted genes with flanks and clustered them into discrete haplotypes.")

    # Step 4: Align paired-end reads to database genes with surrounding flanks
    bowtie2_outdir = outdir + 'Bowtie2_Alignments/'
    if not os.path.isfile(bowtie2_outdir): os.system('mkdir %s' % bowtie2_outdir)
    logObject.info("")
    #lsaBGC.runBowtie2Alignments(bowtie2_reference, paired_end_sequencing_file, bowtie2_outdir, cores, logObject)
    logObject.info("")

    # Step 5: Determine haplotypes found in samples and identify supported novelty SNVs
    results_outdir = outdir + 'Parsed_Results/'
    if not os.path.isdir(results_outdir): os.system('mkdir %s' % results_outdir)
    logObject.info("")
    #lsaBGC.runSNVMining(cog_genes, comp_gene_info, bowtie2_reference, paired_end_sequencing_file, instances_to_haplotypes, bowtie2_outdir, results_outdir, cores, logObject)
    logObject.info("")

    # Step 6: Construct summary matrices
    logObject.info("")
    lsaBGC.createSummaryMatricesForMetaNovelty(paired_end_sequencing_file, results_outdir, outdir, logObject)
    logObject.info("")

    # Step 7: Create Novelty Report
    logObject.info("")
    lsaBGC.generateNoveltyReport(results_outdir, codon_alignments_file, cog_prop_multicopy, comp_gene_info, outdir, logObject)
    logObject.info("")

    # Close logging object and exit
    lsaBGC.closeLoggerObject(logObject)
    sys.exit(0)

if __name__ == '__main__':
    lsaBGC_RelativeDivergance()