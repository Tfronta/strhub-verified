## About

MPSproto is a tool which contains a quantitative model for MPS-STR data to deal with complex stutters.

## Installation

Installation for Windows (http://www.euroformix.com/MPSproto): 
install.packages('http://www.euroformix.com/sites/default/files/MPSproto_0.9.7.zip',repos=NULL,type='win.binary')

Alternative installation from Github (https://github.com/oyvble/MPSproto): \
install_github("oyvble/MPSproto")

## Get started using GUI
Open R and run
``` r
library(MPSproto) #load package
pkg = path.package("MPSproto") #get package install folder
proj = paste0(pkg,"/examples/proj.Rdata") #obtain project file
gui(proj)
```

## Other information

Mathematical details of the model and a tutorial for how to use the tool can be found in the doc folder.

The tool was first time mentioned in the discussion of the paper Agudo et al (2022): "A comprehensive characterization of STR-MPS stutter artefacts". 
- Folder MPSproto_stutterCharPaper in the MPSproto installation directory contains scripts for the calibration and examples of interpretation

The allele format for MPS data must be the "Forward_Strand_Bracketed_form" from LUSstr (https://github.com/bioforensics/lusSTR) or LUSstrR (https://github.com/oyvble/LUSstrR).

An explanation about the nomenclature of the different stutter types used in the program:
- BW1= ‘n-1’ for longest motif-repeat
- FW1= ‘n+1’ for longest motif-repeat
- DBW1= ‘n-2’ for longest motif-repeat (double back stutter)
- TBW1= ‘n-3’ for longest motif-repeat (tripple back stutter)
- etc.. 

For more complex sequences:
- BW2= ‘n-1’ for second longest motif-repeat
- FWBW= ‘n+1’ for longest motif-repeat and ‘n-1’ for second longest motif-repeat
- BWFW= ‘n-1’ for longest motif-repeat og ‘n+1’ for second longest motif-repeat

The software also support traditional CE data, with stutters BW1, FW1, DBW1 as supported stutter types.

