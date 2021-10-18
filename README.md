# Graph-Part
Protein dataset partitioning pipeline (Gíslason 2021)

Graph-Part is a Python package for generating partitions (i.e. train-test splits) of biological sequence datasets. It ensures minimal homology between different partitions, while balancing partitions for labels or other desired criteria.

## Test installation
```
conda install -c bioconda emboss
git clone https://github.com/fteufel/graph-part.git
cd graph-part
pip install .
```

## Installation - WIP

Graph-Part relies on [needleall](https://www.bioinformatics.nl/cgi-bin/emboss/help/needleall) from the [EMBOSS](http://emboss.sourceforge.net/) package for fast Needleman-Wunsch alignments of sequences. Please refer to the official EMBOSS documentation for installation methods.

We recommend to install Graph-Part in a conda environment, and install EMBOSS from [bioconda](https://anaconda.org/bioconda/emboss) via 
```
conda install -c bioconda emboss
```

Alternatively, on Ubuntu, EMBOSS is available directly via `sudo apt-get install emboss` .

To install Graph-Part, run
```
pip install graphpart
```
The command `graphpart` will now be available on your command line.

## Instructions
As an example, this is a basic command for partitioning a dataset at a maximum pairwise cross-partition identity of 30% into 5 folds. The resulting partitions are balanced for equal frequencies of the class labels specified in `label=` in the FASTA headers. `--threads` can be adapted according to your system and has no effect on the partitioning itself.
```
graphpart  --fasta-file netgpi_dataset.fasta --threshold 0.3 --out-file graphpart_assignments.csv --labels-name label --partitions 5 --threads 12
```


## Input format
Graph-Part works on FASTA files with a custom header format, e.g.
```
>P42098|label=CLASSA|priority=0
MAPSWRFFVCFLLWGGTELCSPQPVWQDEGQRLRPSKPPTVMVECQEAQLVVIVSKDLFGTGKLIRPADL
>P0CL66|label=CLASSB|priority=1
MKKYLLGIGLILALIACKQNVSSLDEKNSVSVDLPGEMKVLVSKEKNKDGKYDLIATVDKLELKGTSDKN
```
Alternatively , `:` and &nbsp;`-`&nbsp; (note there are spaces on either side of the `-`) can be used as separators instead of `|`. It should be taken care that the sequence identifiers themselves contain no separator symbols. The keywords `label` and `priority` can be customized by specifying the `--labels-name` and `--priority-name` arguments. Both elements of the header are optional, Graph-Part can also just partition based on sequences alone, without any class balancing. (TODO untested?)  
You can find a script to convert `.csv` datasets into the custom `.fasta` format at [csv_to_fasta.py](csv_to_fasta.py)


## TODO

- Write tool to make fasta from assignments (concatenate assignment to header, seperator of choice)
- Write tool to make fasta from .csv (specifify spearator, label_col (multiple?) and priority_col)
- Fix alignment of header in removal output - this seems to happen with large Connectivity values:  
```
Min-threshold    #Entities       #Edges          Connectivity    #Problematics   #Relocated      #To-be-removed  
0.01             3539            411624                  460915                  3517            1856            1  
```

## API

Long                    | Short | Description
------------------------|-------|------------
`--fasta-file`          |`-ff`  | Path to the input fasta file, formatted according to [the input format](#Input-format).
`--out-file`            |`-of`  | Path at which to save the partition assignments as `.csv`
`--threshold`           |`-th`  | The desired partitioning threshold, should be within the bounds defined by the metric.
`--partitions`          |`-pa`  | Number of partitions to generate.
`--transformation`      |`-tf`  | Transformation to apply to the similarity/distance metric. Graph-Part operates on distances, therefore similarity metrics need to be transformed. Can be any of `one-minus`, `inverse`, `square`, `log`, `None`. See the [source](graph_part/transformations.py) for definitions. As an example, when operating with sequence identities ranging from 0 to 1, the transformation `one-minus` yields corresponding distances. Defaults to `one-minus`.
`--denominator`         |`-dn`  | Denominator to use for percent sequence identity computation. The number of perfect matching positions is divided by the result of this operation. Can be any of `shortest`, `longest`, `mean`, `full`, `no_gaps`. The first three options are computed from the original lengths of the aligned sequences. `full` refers to the full length of the alignment, including gaps, and is the default. `no_gaps` subtracts gaps from the full alignment length.
`--priority-name`       |`-pn`  | The name of the priority in the meta file. TODO what does this do
`--labels-name`         |`-ln`  | The name of the label in the meta file. Used for balancing partitions.
`--initialization-mode` |`-im`  | Use either slow or fast restricted nearest neighbor linkage or no initialization. Can be any of `slow-nn`, `fast-nn`, `simple`. Defaults to `slow-nn`.
`--threads`             |`-nt`  | The number of threads to run in parallel. If `None`, will use all available resources. Defaults to 1.
`--chunks`              |`-nc`  | The number of chunks into which to split the fasta file for multithreaded alignment. Defaults to 10.
`--load_checkpoint_path`|`-lc`  | Optional path to save the generated graph. Defaults to `None` with no graph saved.
`--save_checkpoint_path`|`-sc`  | Optional path to a previously generated graph for quickstart. If provided, no alignment will be performed and all arguments relating to this step are ignored.
`--edge-file`           |`-ef`  | Optional path to a comma separated file containing precomputed pairwise metrics, the first two columns should contain sequence identifiers specified in the  `--fasta-file`. This is can be used to run Graph-Part with an alignment tool different from the default `needleall`.
`--metric-column`       |`-mc`  | When using `--edge-file`, specifies in which column the metric is found. Indexing starts at 0, defaults to 2 when left unspecified.

**Flags** 
Long                    | Short | Description
------------------------|-------|------------
`--no-moving`           |`-nm`  | By default, the removing procedure tries to relocate sequences to another partition if it finds more within-threshold neighbours in any. This flag disallows moving.
`--remove-same`         |`-rs`  | This here is the inverse of removal_type (has default True), not sure what it does TODO
`--nucleotide`          |`-nu`  | Use this flag if the input contains nucleotide sequences. By default, assumes proteins.
`--triangular`          |`-tr`  | Only compute triangular of the full distance matrix. Twice as fast, but can yield slightly different results if an alignment has two different solutions with the same score, but different identities.

**Parameters passed to `needleall`** 
Long                    | Alternative (original name) | Description
------------------------|---------------|------------
`--gapopen`             |`-gapopen`     | [10.0 for any sequence] The gap open penalty is the score taken away when a gap is created. The best value depends on the choice of comparison matrix. The default value assumes you are using the EBLOSUM62 matrix. (Floating point number from 1.0 to 100.0)
`--gapextend`           |`-gapextend`   | [0.5 for any sequence] The gap extension penalty is added to the standard gap penalty for each base or residue in the gap. This is how long gaps are penalized. Usually you will expect a few long gaps rather than many short gaps, so the gap extension penalty should be lower than the gap penalty. An exception is where one or both sequences are single reads with possible sequencing errors in which case you would expect many single base gaps. You can get this result by setting the gap open penalty to zero (or very low) and using the gap extension penalty to control gap scoring. (Floating point number from 0.0 to 10.0)
`--endextend`           |`-endextend`   | [0.5 for any sequence] The end gap extension, penalty is added to the end gap penalty for each base or residue in the end gap. This is how long end gaps are penalized. (Floating point number from 0.0 to 10.0)
`--endweight`           |`-endweight`   | Flag. Apply end gap penalties.
`--endopen`             |`-endopen`     | [10.0 for any sequence] The end gap open penalty is the score taken away when an end gap is created. The best value depends on the choice of comparison matrix. The default value assumes you are using the EBLOSUM62 matrix for protein sequences. (Floating point number from 1.0 to 100.0)
`--matrix`              |`-datafile`    | This is the scoring matrix file used when comparing sequences. By default it is the file 'EBLOSUM62'. These files are found in the 'data' directory of the EMBOSS installation.


## FAQ
WIP
- **How should I pick `chunks` ?**  
`chunks` should be picked so that all `threads` are utilized. Each chunk is aligned to each other chunk, so `threads` <= `chunks`*`chunks` results in full utilization.

- **I want to test multiple thresholds - How can I do this efficiently ?**  
When constructing the graph, we only retain distances that are smaller than the selected `threshold`, as only those form relevant edges for partitioning the data. All other distances are discarded as they are computed. To test multiple thresholds, the most efficient way is to first try the highest threshold to be considered (when working with sequence identities, this means the lowest sequence identity) and activate checkpointing of the graph by specifiying `--save-checkpoint-path`. In the next run, use `--load-checkpoint-path` to start from your saved graph and avoid recomputing the edges. 

