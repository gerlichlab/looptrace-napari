# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2024-04-15

### Changed
__Locus spots visualisation__
* QC-failed points are now...
    * only text, no actual point
    * sky blue rather than standard blue
* QC-passed points are now...
    * goldenrod/dandelion yellow rather than red
* Color changes have been made to be more [colorblind-friendly](https://davidmathlogic.com/colorblind/).
* Points (or text) are now visible throughout each $z$-stack, rather than just in the slice nearest the center of the Gaussian fit.
* Each QC-pass point's position in $xy$ is shown as a stars in the $z$-slice corresponding to the truncation of the $z$-coordinate of the center of its Gaussian fit; it's shown in other slices as a circle.
* Each QC-pass point is 50% larger in the $z$ slice corresponding to the center of its fit.

## [0.2.0] - 2024-04-14

### Added
* Visualisation of [nuclear masks](./looptrace_napari/nuclei_reader.py)
* [Documentation](./docs/)
* Beginnings of a [test suite](./tests/)
* [Nix shell](./shell.nix) for user and test environments

## [0.1.0] - 2024-04-08

### Added
* This package, under name `looptrace-napari`. 
