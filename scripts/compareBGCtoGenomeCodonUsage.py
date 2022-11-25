import os
import sys
from Bio import SeqIO
from Bio.Seq import Seq
import argparse
from collections import defaultdict
from scipy import stats, spatial

def create_parser():
    """ Parse arguments """
    parser = argparse.ArgumentParser(description="""
	Program: compareBGCtoGenomeCodonUsage.py
	Author: Rauf Salamzade
	Affiliation: Kalan Lab, UW Madison, Department of Medical Microbiology and Immunology
		
	This program compares the codon-usage distribution of a BGC (provided as a Genbank) to the codon usage of the 
	background genome (gathered from a full-genome Genbank file - also an output of antiSMASH). It will report
	the cosine distance and Spearman correlation between the two profiles. Only ORFs which are of length divisible 
	by 3 will be considered. It can accept multiple BGC Genbanks in the case that the BGC is fragmented across 
	multiple scaffolds.
	
	Only works for bacterial genomes currently.
	""", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-g', '--full_genome_genbank', help="Path to annotated full-genome Genbank for isolate's genome.", required=True, default=None)
    parser.add_argument('-b', '--bgc_genbanks', nargs='+', help="Path to BGC Genbank(s) for isolate. Locus tags must match with tags in full-genome Genbank.", required=True, default=None)
    parser.add_argument('-o', '--output', help="Path to output file.", required=True, default=None)
    args = parser.parse_args()
    return args

valid_bases = set(['A', 'C', 'G', 'T'])
def main():
    """
    Void function which runs primary workflow for program.
    """

    """
    PARSE REQUIRED INPUTS
    """
    myargs = create_parser()

    full_genbank = os.path.abspath(myargs.full_genome_genbank)
    bgc_genbanks = myargs.bgc_genbanks
    output = os.path.abspath(myargs.output)

    try:
        assert(os.path.isfile(full_genbank))
        assert(sum([1 for x in bgc_genbanks if os.path.isfile(x)]) == len(bgc_genbanks))
    except:
        raise RuntimeError('One or more input files do not exist. Exiting now ...')

    """
    START WORKFLOW
    """

    # parse Genbanks of BGCs
    gcf_lts = set([])
    for gbk in bgc_genbanks:
        with open(gbk) as ogbk:
            for rec in SeqIO.parse(ogbk, 'genbank'):
                for feature in rec.features:
                    if not feature.type == 'CDS': continue
                    locus_tag = feature.qualifiers.get('locus_tag')[0]
                    gcf_lts.add(locus_tag)

    # parse nucleotide coding sequences from full-genome Genbank
    locus_tag_sequences = {}
    with open(full_genbank) as ofgbk:
        for rec in SeqIO.parse(ofgbk, 'genbank'):
            full_sequence = str(rec.seq)
            for feature in rec.features:
                if not feature.type == 'CDS': continue
                locus_tag = feature.qualifiers.get('locus_tag')[0]
                start = min([int(x.strip('>').strip('<')) for x in str(feature.location)[1:].split(']')[0].split(':')]) + 1
                end = max([int(x.strip('>').strip('<')) for x in str(feature.location)[1:].split(']')[0].split(':')])
                direction = str(feature.location).split('(')[1].split(')')[0]

                nucl_seq = ''
                if end >= len(full_sequence):
                    nucl_seq += full_sequence[start - 1:]
                else:
                    nucl_seq += full_sequence[start - 1:end]
                if direction == '-':
                    nucl_seq = str(Seq(nucl_seq).reverse_complement())
                locus_tag_sequences[locus_tag] = nucl_seq

    # get codon frequencies for CDS in BGC and background genome
    cod_freq_dict_gcf = defaultdict(int)
    cod_freq_dict_background = defaultdict(int)
    all_cods = set([])
    for locus_tag in locus_tag_sequences:
        seq = locus_tag_sequences[locus_tag]
        if not len(str(seq))%3 == 0:
            sys.stderr.write("The locus tag %s is ignored because it was not of length 3.\n" % locus_tag)
            continue
        codon_seq = [str(seq)[i:i + 3] for i in range(0, len(str(seq)), 3)]
        for cod in list(codon_seq):
            if not(len(cod) == 3 and cod[0] in valid_bases and cod[1] in valid_bases and cod[2] in valid_bases): continue
            if locus_tag in gcf_lts:
                cod_freq_dict_gcf[cod] += 1
            else:
                cod_freq_dict_background[cod] += 1
            all_cods.add(cod)

    cod_order = []
    gcf_cod_freqs = []
    bkg_cod_freqs = []
    for cod in sorted(all_cods):
        cod_order.append(cod)
        gcf_cod_freqs.append(cod_freq_dict_gcf[cod])
        bkg_cod_freqs.append(cod_freq_dict_background[cod])

    # compute stats
    rho, spm_pval, cosine_distance = ["NA"]*3
    try:
        rho, spm_pval = stats.spearmanr(gcf_cod_freqs, bkg_cod_freqs)
        cosine_distance = spatial.distance.cosine(gcf_cod_freqs, bkg_cod_freqs)
    except:
        sys.stderr.write('Issues with computing stats!\n')

    output_handle = open(output, 'w')
    output_handle.write('Cosine_Distance\t%f\n' % round(cosine_distance, 3))
    output_handle.write('Spearman_Rho\t%f\n' % round(rho, 3))
    output_handle.write('Spearman_Pvalue\t%f\n' % round(spm_pval, 3))
    output_handle.write('GCF_Codons\t%s\n' % ', '.join(cod_order))
    output_handle.write('GCF_Codon_Frequencies\t%s\n' % ', '.join([str(x) for x in gcf_cod_freqs]))
    output_handle.write('Background_Codon_Frequencies\t%s\n' % ', '.join([str(x) for x in bkg_cod_freqs]))
    output_handle.close()

    sys.exit(0)

if __name__ == '__main__':
    main()
