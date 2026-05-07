# graphLUT

Samples output channel curves from a 3D LUT in `.cube` format.

The script sweeps one input channel across a range, evaluates the LUT at each step using tetrahedral interpolation, and writes the sampled R/G/B outputs to a CSV file. It can optionally produce a plot via matplotlib or as a self-contained SVG/PNG with no extra dependencies.

Input values are remapped through:

$$\text{remapped} = \frac{876 \times v + 64}{1023}$$

This maps a float to the legal code range `[64/1023, 940/1023]`. Values <0 go below 64 and >1 go above 940.

## Requirements

- Python 3.10+
- `matplotlib` (optional, only required for `--plot` or non-SVG `--plot-output`)

## Usage

```
python graphLUT.py <cube_file> [options]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `cube_file` | *(required)* | Input `.cube` file (3D LUTs only). |
| `--output PATH` | `lut_curve.csv` | Output CSV file path. |
| `--channel {r,g,b}` | `r` | Input channel to sweep along the x axis. |
| `--start VALUE` | `0.0` | Start of the sweep range, remapped before use. |
| `--end VALUE` | `1.0` | End of the sweep range, remapped before use. |
| `--samples N` | `256` | Number of evenly-spaced sample points. |
| `--fixed-rgb R G B` | `0.0 0.0 0.0` | Fixed values for the two channels not being swept. Each is remapped before use. |
| `--plot` | off | Open an interactive matplotlib window. |
| `--plot-output PATH` | *(none)* | Save the plot to a file. Use `.svg` extension for no matplotlib dependency. |
| `--plot-single-channel` | off | Plot only the output channel matching `--channel` instead of all three. |

## Examples

### Basic usage -- sweep R, write CSV

```bash
python graphLUT.py film.cube
```

Produces `lut_curve.csv` with columns `x, out_r, out_g, out_b`.

### Save to a specific CSV path

```bash
python graphLUT.py film.cube --output film_r_curve.csv
```

### Sweep the green channel

```bash
python graphLUT.py film.cube --channel g --output film_g_curve.csv
```

### Sweep over a sub-range

```bash
python graphLUT.py film.cube --start 0.2 --end 0.8
```

### Fix the non-swept channels at mid-grey

```bash
python graphLUT.py film.cube --channel r --fixed-rgb 0.5 0.5 0.5
```

### Show an interactive plot with matplotlib

```bash
python graphLUT.py film.cube --plot
```

### Save plot as PNG (requires matplotlib)

```bash
python graphLUT.py film.cube --plot-output film_curve.png
```

### Save plot as SVG (no matplotlib needed)

```bash
python graphLUT.py film.cube --plot-output film_curve.svg
```

### Show interactive plot and also save as SVG

```bash
python graphLUT.py film.cube --plot --plot-output film_curve.svg
```

### Plot only the swept channel's output

```bash
python graphLUT.py film.cube --channel g --plot --plot-single-channel
```

### Full example with all options

```bash
python graphLUT.py film.cube \
    --channel b \
    --start 0.1 \
    --end 0.9 \
    --samples 512 \
    --fixed-rgb 0.5 0.5 0.0 \
    --output film_b_curve.csv \
    --plot \
    --plot-output film_b_curve.svg \
    --plot-single-channel
```

## Output CSV format

| Column | Description |
|---|---|
| `x` | Input value (remapped) |
| `out_r` | LUT output R at this input |
| `out_g` | LUT output G at this input |
| `out_b` | LUT output B at this input |

## Notes

- Only 3D `.cube` LUTs are supported. 1D LUTs (`LUT_1D_SIZE`) will raise an error.
- `DOMAIN_MIN` / `DOMAIN_MAX` in the `.cube` file are respected.
- When `--plot-output` points to an `.svg` file and `--plot` is not set, the SVG is written directly without invoking matplotlib.
- When matplotlib is not installed and a non-SVG output path is requested without `--plot`, the script falls back to writing an SVG at the same path with a `.svg` extension.
