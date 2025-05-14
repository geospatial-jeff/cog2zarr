# cog2zarr

COG to Zarr v3 translator.  I have a few motivations for writing this:
- Become more familiar with the Zarr v3 spec (learn by doing).
- Establish a conceptual model between COG and Zarr V3 and a reference example to help geozarr development, with as little abstraction as possible to keep things simple.
- Play around with coordinate system representation (affine + crs) in the context of (rio)xarray.
- Determine how fast / cheap this translation is.  Moving tiles from one place to another is an embarassingly horizontal problem, and should be memory efficient if we implement streaming in async-tiff.

At a high level, I'd like to implement four different "configurations".  Imagine a single one-band COG that is 1024x1024 pixels with 256x256 chunks, and no overviews to keep things simple.  There are several possible configurations in zarr:
1. Each 256x256 tile in the COG becomes a single 256x256 chunk in the zarr array.  This is the easiest to implement, and the most direct translation in my opinion.
2. The 1024x1024 COG becomes a single sharded zarr chunk with 256x256 inner chunks; 16 in total.
3. Somewhere between (1) and (2).  The COG turns into 4 sharded zarr chunks; each chunk is 512x512 with 4 256x256 inner chunks.
4. The entire 1024x1024 COG becomes a single 1024x1024 chunk in the zarr array.  Compositing multiple COGs into a single zarr array.
