# ansys-micromechanics

# Installation

Clone the repository using:

```
git clone https://github.com/CMSM-VCU/ansys-micromechanics.git
```

The Git software can be downloaded from [here](https://git-scm.com/downloads).

## Activating the Virtual Environment

After you have upgraded your version of Anaconda, you can activate the conda environment for this program by running the following commands (**IMPORTANT:** make sure you are in the <code>ansys-micromechanics</code> directory, which contains the file <code>environment.yml</code>):

```
conda env create -f environment.yml
conda activate ansys-micro
```

At this point, you should see a prefix in your terminal that looks something like <code>(ansys-micro) username@device %</code>. This signifies that your virtual environment is working and you are using it currently.

Now that all of the dependencies are set up, you are ready to run the program!

## Updating the Virtual Environment

Once you have created the virtual environment, there may be adjustments to the packages included in <code>environment.yml</code>. Instead of recreating the virtual environment every time this happens, you can easily update the virtual environment by running the following command after the new YAML file is downloaded:

```
conda env update -f environment.yml --prune
```

You'll notice that this is very similar to the command used to create the virtual environment, but with "update" in lieu of "create." Adding <code>--prune</code> ensures that if a requirement is removed from <code>environment.yml</code>, it is also removed from the virtual environment once you update it.

From there, you can activate/deactivate the virtual environment as normal.

# Usage

## Running the Program

This program runs in Python 3.8 or higher, which was installed in the conda environment. The program must be executed inside the `ansys-micromechanics` directory. The program reads input from JSON files. The paths to these files must be included as command line arguments when the program is executed, like so:

```
python main.py relative/path/to/file.json
```

Multiple input files can be run in sequence by including multiple paths:

```
python main.py relative/path/to/file1.json relative/path/to/file2.json
```

The absolute path to an input file can also be used, as well as either forward slashes `/` or back slashes `\`.

```
python main.py C:\absolute\path\to\file.json
```

If the path or filename contains spaces, wrap the path in quotes:

```
python main.py "relative/path/with spaces/to/file with spaces.json"
```

## Input File Format

The input files use the standard JSON format and are validated using a schema.

# Background Summary

[See here](https://www.notion.so/Ansys-Micromechanics-Background-Summary-cbcfac8c0d2f4c3eac8476f963047e3b) for a summary of the method being applied by this tool.
