# Schemonic

Compress database schemata to reduce cost for LLM processing

## Preparing Experiments

Tested with c5.4xlarge EC 2 instance with Ubuntu 22.04 installed. All commands are executed from Ubuntu user home directory.

1. Download benchmark schemata [here](https://drive.google.com/file/d/1KrXwsJKv0L2J9p24cYkvyDxQyfRn5BD-/view?usp=sharing).
2. Install Gurobi for Python: `sudo pip install gurobipy`
3. Download Gurobi solver (tested with version 10.0.3): `wget https://packages.gurobi.com/10.0/gurobi10.0.3_linux64.tar.gz`
4. Unpack Gurobi solver: `tar xvfz gurobi10.0.3_linux64.tar.gz`
5. Add the following to your `.bashrc` file:
```
export GUROBI_HOME="/home/ubuntu/gurobi1003/linux64"
export PATH="${PATH}:${GUROBI_HOME}/bin"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${GUROBI_HOME}/lib"
```
6. Re-read the changed file: `source .bashrc`.
7. Check that Gurobi is installed: `gurobi_cl --version`.
8. Install a license to enable solving large problems. E.g., the experiments used a Gurobi academic license WLS. For this license, download the `gurobi.lic` file and copy it into the home directory of the server executing optimization.

## Evaluating Compression Methods

Use `src/sc/benchmark/performance.py` to compare different schema compression methods in terms of their run time and compression ratio. The script takes the following command line parameters:

| Parameter | Explanation |
| --- | --- |
| inputdir | Path to directory containing .sql files with schema definitions |
| timeout_s | Timeout in seconds per test case and per compression baseline |
| outpath | Path to .json file with benchmark results to be created |

Optionally, users can specify the following flags for ablation studies:

| Flag | Explanation |
| --- | --- |
| --nostart | Do not use greedy solutions as ILP start |
| --nohints | Do not specify hints for ILP variables |
| --nomerge | Do not merge column annotations together |
