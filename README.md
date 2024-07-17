# BELTRANS gephi extraction

A script to extract node and edge lists from the BELTRANS corpus Excel file. Deliberately not a command line script with parameters, because the users would like to use variables instead. 

## Usage

**(1) Create and activate a Python virtual environment**

```bash
# Create a new Python virtual environment
python3 -m venv py-gephi-extraction-env

# Activate the virtual environment
source py-gephi-extraction-env/bin/activate

# Install dependencies
pip -r requirements.txt

```

**(2) Adapt the necessary parameters in the script.**

* `inputFile`: the full path to the input Excel file
* `genrePrefixes`: A string used to filter Belgian Bibliography genre classifications. Examples are provided in the script
* `minYear`  and `maxYear`: values used to filter publications of the input data
* `considerImprintRelation`: `True` or `False`, indicating if indicated publishers (imprints) are used as nodes or if they should be replaced with their main publisher as indicated in the `isImprintOf` column
* `imprintMappingExceptions`: identifiers of imprints that should not be replaced with their main publisher
* `namesInsteadOfIdentifiers`: use the name of nodes as identifier (both in nodes and in edges), if duplicate names are found a warning is printed

> [!NOTE]
> Please note that normally such things are down via command line parameters or a config file.
> However, users of this script preferred to change variables instead.

**(3) Execute the script**

```
python gephi-extraction.py
```

## Dependencies

All dependencies are listed in the file `requirements.txt`.
This script uses Pandas. More specifically the function `read_excel` is used which requires the other dependencies.
