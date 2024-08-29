#
#  This file is part of Sequana software
#
#  Copyright (c) 2021-2022 - Sequana Dev Team (https://sequana.readthedocs.io)
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  Website:       https://github.com/sequana/sequana
#  Documentation: http://sequana.readthedocs.io
#  Contributors:  https://github.com/sequana/sequana/graphs/contributors
##############################################################################
import os
import sys

import click_completion
import rich_click as click

click_completion.init()

NAME = "lora"


import rich_click as click
from sequana_pipetools import SequanaConfig, SequanaManager, logger, levenshtein_distance, download_and_extract_tar_gz

from sequana_pipetools.options import (
    ClickGeneralOptions,
    ClickInputOptions,
    ClickSlurmOptions,
    ClickSnakemakeOptions,
    include_options_from,
    init_click,
)

from .info import checkm
from .info import busco
from .src import utils

NAME = "lora"

help = init_click(
    NAME,
    groups={
        "Pipeline Specific": [
            "--assembler",
            "--genome-size",
            "--data-type",
            "--blastdb",
            "--bacteria",
            "--do-circlator",
            "--do-correction",
            "--do-coverage",
            "--mode",
        ],
        "Pipeline Specific Completeness": ["--checkm-rank", "--checkm-name", "--busco-lineage"],
        "Pipeline Specific Pacbio": ["--pacbio-input-csv", "--pacbio-ccs-min-passes", "--pacbio-ccs-min-rq", "--pacbio-build-ccs"],
    },
)


class ChoiceOrDir(click.ParamType):
    name = "choice_or_dir"
    def __init__(self, choices):
        self.choices = choices
    def convert(self, value, param, ctx):
        if value in self.choices:
            return value
        if os.path.isdir(value):
            return value

        guesses = [x for x in busco if levenshtein_distance(value, x.lower())<5]
        self.fail(f"{value} is not a valid choice or file path. Maybe you meant {guesses}", param, ctx)
# 
BUSCO_OR_DIR = ChoiceOrDir(busco.keys())


@click.command(context_settings=help)
@include_options_from(ClickSnakemakeOptions, working_directory=NAME)
@include_options_from(ClickSlurmOptions, profile="local")
@include_options_from(ClickInputOptions, add_input_readtag=False, input_pattern="*fastq.gz")
@include_options_from(ClickGeneralOptions)
@click.option(
    "--pacbio-input-csv",
    "input_csv",
    help="Simple CSV file with the samples names and files. LORA will generate CCS and merge your files."
    " If you do not want to do CCS, you can put only one file for each samples.",
)
@click.option(
    "--assembler",
    "assembler",
    type=click.Choice(["canu", "hifiasm", "flye", "unicycler"]),
    required=True,
    help="An assembler in canu, hifiasm, flye (unicycler not yet implemented). We recommend flye that also performs circularisation.",
)
@click.option(
    "--genome-size",
    "genome_size",
    type=click.STRING,
    required=True,
    help="A estimate of the genome size. For canu, this is used only to report depth of coverage. For flye, this is higly recommended so we make it compulsary in LORA. You can use 'm' or 'g' letter to indicate mega and giga bases, e.g., 5m, 2g.",
)
@click.option(
    "--mode",
    "mode",
    default="default",
    type=click.Choice(["default", "eukaryotes", "bacteria"]),
    show_default=True,
    help="If mode is set to 'bacteria', blast, circlator, busco, prokka, sequana_coverage, checkm are ON."
    " If mode is set to eukaryotes, only blast and busco tasks are ON. Default sets all these tasks OFF.",
)
@click.option(
    "--do-correction",
    "do_correction",
    is_flag=True,
    help="Run canu correction before hifiasm or flye.",
)
@click.option(
    "--pacbio-build-ccs",
    "do_ccs",
    is_flag=True,
    help="""If your input is made of raw Pacbio BAM with no consensus (subreads), we recommend you to construct consensus
file (CCS) from the subreads.bam files. By default min-passes is set to 10 and min-rq to 0.99 to build so-called HiFi
reads. You can replace this values using --pacbio-ccs-min-passes and --pacbio-ccs-min-rq options""",
)
@click.option(
    "--data-type",
    "data_type",
    type=click.Choice(["pacbio", "nanopore"]),
    required=True,
    help="Tells LORA that the input data is made of nanopore or pacbio data.",
)
@click.option(
    "--do-circlator",
    "do_circlator",
    is_flag="store_true",
    help="Run circlator after assembler. Use with canu assembler.",
)
@click.option("--do-coverage", "do_coverage", is_flag="store_true", help="Run sequana coverage on contigs.")
@click.option("--blastdb", "blastdb", help="Path to your blast database")
@click.option(
    "--busco-lineage",
    "lineage",
    type=BUSCO_OR_DIR,
    help="Lineage or path to lineage file for BUSCO. Note that we support only version 5 of the BUSCO lineage. If the lineage is not a valid path, we download it locally. This may take time. Full list is on https://github.com/sequana/lora//wiki/busco",
)
@click.option(
    "--checkm-rank",
    default="genus",
    show_default=True,
    type=click.Choice(checkm['ranks']),
    help="For bacteria, checkm can be used. Usually at the genus level. can be set to 'domain', 'phylum', 'class', 'order', 'family', 'genus', 'species'. ",
)
@click.option(
    "--checkm-name",
    type=str,
    default=None,
    help="Valid checkm taxon name. This depends on the rank provided with --checkm-rank. Please have a look at this page on LORA wiki page here: https://github.com/sequana/lora/wiki/checkm ; you may also set --checkm-rank and type any invalid values to get a list of valid names",
)
@click.option(
    "--pacbio-ccs-min-passes",
    default=10,
    show_default=True,
    type=click.INT,
    help="minimum number of passes required to build the CCS. Set to 10 for HIFI quality",
)
@click.option(
    "--pacbio-ccs-min-rq",
    default=0.99,
    show_default=True,
    type=click.FLOAT,
    help="minimum quality required to build the CCS. Set to 0.99 for HIFI quality",
)
def main(**options):
    """ """
    # the real stuff is here
    manager = SequanaManager(options, NAME)
    options = manager.options

    # creates the working directory
    manager.setup()

    cfg = manager.config.config

    # use profile slurm if user set a slurm queue
    if options.slurm_queue != "common":
        options.profile = "slurm"

    # fill the config file with input parameters
    cfg = manager.config.config
    cfg.input_directory = os.path.abspath(options.input_directory)
    cfg.input_pattern = options.input_pattern
    cfg.input_csv = os.path.abspath(options.input_csv) if options.input_csv else ""

    preset_dir = utils.LORA_PATH / "presets"

    # Default parameters are for pacbio. There is no pacbio presets
    if options.data_type == "nanopore":
        nano = SequanaConfig(str(preset_dir / "nanopore.yml"))
        cfg.update(nano.config)

    # load default optionse for bacteria or eukaryotes or the default
    if options.mode == "bacteria":  # default (nothing to do)
        mode_cfg = SequanaConfig(str(preset_dir / "bacteria.yml"))
        cfg.update(mode_cfg.config)
        if options.data_type == "nanopore":
            cfg["quast"]["preset"] = "nanopore"
    elif options.mode == "eukaryotes":  # default (nothing to do)
        mode_cfg = SequanaConfig(str(preset_dir / "eukaryote.yml"))
        cfg.update(mode_cfg.config)

    # checkm
    if options.checkm_name:
        cfg.checkm["do"] = True
        cfg.checkm["taxon_rank"] = options.checkm_rank

        # check checkM  taxon name
        valid_taxon = checkm[options.checkm_rank]
        if options.checkm_name not in valid_taxon:
            guesses = [x for x in valid_taxon if levenshtein_distance(options.checkm_name.lower(), x.lower())<5]
            msg = f"CheckM issue. For the provided rank ({options.checkm_rank}), you set an unknown name: {options.checkm_name}. Please check the list on https://github.com/sequana/lora/wiki/checkm."
            if len(guesses):
                msg += f" Maybe you meant one of: {guesses}, Please use the proper lower/upper case"
            logger.error(msg)
            sys.exit(1)
        else:
            # Note the quotes to include spaces within a valid string for the species
            cfg.checkm["taxon_name"] = f"{options.checkm_name}"

    # The user may overwrite the default
    if options.do_circlator:
        cfg.circlator["do"] = options.do_circlator

    if options.blastdb:
        cfg.blast["blastdb"] = options.blastdb
        cfg.blast["do"] = True

    if options.lineage:
        cfg.busco['do'] = True
        if os.path.isdir(options.lineage):
            cfg.busco["lineage"] = options.lineage
        else:
            # if not a directory, we need to download the dataset locally.
            logger.info(f"Download {options.lineage} locally for BUSCO analysis")
            url = busco[options.lineage]
            download_and_extract_tar_gz(url, f"{manager.workdir}/busco_downloads")
            cfg.busco["lineage"] = f"busco_downloads/{options.lineage}_odb10"

    if options.do_coverage:
        cfg.sequana_coverage.do = options.do_coverage

    cfg.canu_correction["do"] = options.do_correction

    # override preset only if user set an assembler
    if options.assembler:
        cfg.assembler = options.assembler

    # handle genome size
    try:
        # is this a number ?
        int(optioms.genome_size)
    except:
        if not options.genome_size.endswith(('k','m','g')):
            logger.error(f"Genome size must end in k, m, g to indicate kilo, mega, giga bases, or a valid integer number. You provided {options.genome_size}")
            sys.exit(1)

        pass

    cfg['canu']['genome_size'] = options.genome_size
    cfg['canu_correction']['genome_size'] = options.genome_size
    cfg['flye']['genome_size'] = options.genome_size 


    # by default, not CCS required. If we have BAM as input, it may be original subreads, in which case you want to do
    # the CCS (possibly) or it coudld already HIFI/CCS data in which case you do not want to dot it. So, we require the
    # user to tell us if he wants to build CCS

    if options.do_ccs:
        cfg.ccs['do'] = True
        if options.data_type == "pacbio" and options.input_pattern.endswith(".bam") is False:
            logger.warning("You chose to build pacbio CCS reads but your input files do not end in .bam ; that's probably not what you want.")
    else:
        cfg.ccs['do'] = False
        cfg.flye['preset'] = "pacbio-corr"

    cfg.ccs["min-rq"] = options.pacbio_ccs_min_rq
    cfg.ccs["min-passes"] = options.pacbio_ccs_min_passes

    # finalise the command and save it; copy the snakemake. update the config
    # file and save it.
    manager.teardown(check_input_files=False)


if __name__ == "__main__":
    main()
