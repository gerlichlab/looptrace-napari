## Locus spots visualisations

### Quickstart
To visualise the locus-specific spots masks, you need to __drag-and-drop files__ into an active Napari window. 
1. First, drag one of the `PXXXX.zarr` files--from the `locus_spots_visualisation` subfolder in your analysis folder from `looptrace`--into Napari.
1. Choose to open the ZARR with the Napari native plugin(s) / readers, not this plugin's.
1. Second, drag a the corresponding (by field of view) pair of `*qcpass.csv` and `*qcfail.csv` files into Napari.
1. Choose to open these QC pass/fail CSVs with this plugin rather than Napari builtins.

### What you should see
A Napari window with a three sliders and three layers (QC pass, QC fail, and pixel data).
- Bottom slider: ROI/trace
- Middle slider: 
- Top slider: 


### Details and troubleshooting
__Scrolling__

In version 0.2 of this plugin, there's an image plane for every z-slice, for every timepoint, for every ROI in the particular field of view. 
This can makes scrolling time-consuming and will be simplified in a future release. 

__Finding points (centers of Gaussian fits to pixel volume)__

In version 0.2 of this plugin, a point (blue or red indicator) can only be visible only in the z-slice closest to the z-coordinate of the the center of the Gaussian fit to a particular pixel volume. Generally, these will be more toward the middle of the z-stack rather than at either end, so focus scrolling mainly through the midrange of the z-axis.
