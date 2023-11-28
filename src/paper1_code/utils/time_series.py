"""Functions that modify (lists of) xarray DataArrays."""

from typing import overload

import cftime
import matplotlib.pyplot as plt
import numpy as np
import scipy
import xarray as xr


def shift_arrays(
    arrays: list[xr.DataArray],
    weighted_ends: float = 1.0,
    ens: str | None = None,
    daily=True,
    custom: int = 0,
) -> list[xr.DataArray]:
    """Shift arrays to make the eruption occur on Feb. 15, 1850.

    Parameters
    ----------
    arrays : list[xr.DataArray]
        A list of xarray DataArrays to shift.
    weighted_ends : float
        Place a weighting on the first and fifth arrays, since they both contribute to
        the same seasonal cycle.
    ens : str, optional
        Choose to shift any list of arrays according to the given ens value. Possible
        values are 'ens1', 'ens2', 'ens3', 'ens4' and 'ens5'.
    daily : bool
        If the data has monthly resolution instead of daily, set this to False
    custom : int
        Choose a custom shift in days that will be applied to all arrays in the list. A
        positive number of 365 will for example shift all dates one year back: 1851 ->
        1850.

    Returns
    -------
    list[xr.DataArray]
        A list of shifted xarray Data Arrays.

    Raises
    ------
    ValueError
        If the weighting on the first and fifth elements is not between 0 and 1.
    """
    array = arrays[:]
    if weighted_ends < 0 or weighted_ends > 1:
        raise ValueError("weighted_ends must be between 0 and 1")
    for i, arr in enumerate(array):
        case_0 = arr.attrs["ensemble"] if ens is None else ens
        match case_0:
            case "ens1":
                shift = 0
                # if weighted_ends != 1.0:
                #     arr.data = arr.data * weighted_ends
            case "ens2":
                # From Feb 15 to May 15
                shift = 89 if daily else 3
            case "ens3":
                # From Fev 15 to Aug 15
                shift = 181 if daily else 6
            case "ens4":
                # From Feb 15 to Nov 15
                shift = 273 if daily else 9
            case "ens5":
                # From Feb 15 to Feb 15
                shift = 365 if daily else 12
                # if weighted_ends != 1.0:
                #     arr.data = arr.data * weighted_ends
            case _:
                print("Don't know how to shift this array.")
                shift = 0
        shift = shift if custom == 0 else custom
        if isinstance(arr.time.data[0], float):
            array[i] = arr.shift(time=-shift).dropna("time")
        else:
            array[i] = arr.shift(time=-shift)
    return list(xr.align(*array))


def _latitude_mean(arr: xr.DataArray, lat: str) -> xr.DataArray:
    """Average over latitude with appropriate weighting."""
    lats = getattr(arr, lat)
    weights = np.cos(np.deg2rad(lats))
    weights.name = "weights"
    return arr.weighted(weights).mean(lat)


@overload
def mean_flatten(
    arrays: list[xr.DataArray], dims: list[str] | None = None
) -> list[xr.DataArray]:
    ...


@overload
def mean_flatten(arrays: xr.DataArray, dims: list[str] | None = None) -> xr.DataArray:
    ...


def mean_flatten(
    arrays: list[xr.DataArray] | xr.DataArray,
    dims: list[str] | None = None,
    lat="lat",
) -> list[xr.DataArray] | xr.DataArray:
    """Average over all longitudes/zonal dimension.

    Parameters
    ----------
    arrays : list[xr.DataArray] | xr.DataArray
        A list of xarray DataArrays to average over.
    dims : list[str], optional
        A list of strings with the dimensions that should be averaged out. Default is
        ["lon", "time"].
    lat : str
        The name that should be used for the latitude dimension. Default is 'lat'.

    Returns
    -------
    list[xr.DataArray] | xr.DataArray
        A list of averaged xarray Data Arrays.
    """
    if dims is None:
        dims = ["lon", "time"]
    try:
        # If latitude is included, it has to be treated with care to make up for
        # changes in grid cells.
        dims.remove(lat)
    except ValueError:
        include_lat = False
    else:
        include_lat = True
    if isinstance(arrays, xr.DataArray):
        if include_lat:
            tmp = _latitude_mean(arrays, lat)
            arrays = tmp.assign_attrs(arrays.attrs)
            tmp.close()
        arrays = arrays.mean(dim=dims)
        arrays = arrays.assign_attrs(arrays.attrs)
        return arrays
    array = arrays[:]
    for i, arr in enumerate(array):
        if include_lat:
            tmp = _latitude_mean(arr, lat)
            arr_ = tmp.assign_attrs(arr.attrs)
            tmp.close()
        else:
            arr_ = arr
        array[i] = arr_.mean(dim=dims)
        array[i] = array[i].assign_attrs(arr_.attrs)
        arr.close()
        arr_.close()
    return array


@overload
def remove_seasonality(
    arrays: list[xr.DataArray],
    freq: float = 1.0,
    radius: float = 0.01,
    plot: bool = False,
) -> list[xr.DataArray]:
    ...


@overload
def remove_seasonality(
    arrays: xr.DataArray,
    freq: float = 1.0,
    radius: float = 0.01,
    plot: bool = False,
) -> xr.DataArray:
    ...


def remove_seasonality(
    arrays: list[xr.DataArray] | xr.DataArray,
    freq: float = 1.0,
    radius: float = 0.01,
    plot: bool = False,
) -> list[xr.DataArray] | xr.DataArray:
    """Remove seasonality from array.

    Parameters
    ----------
    arrays : list[xr.DataArray] | xr.DataArray
        An array or a list of arrays to remove seasonality from
    freq : float
        Gives the frequency that should be removed when using the Fourier method
    radius : float
        Gives the frequency range that should be removed when using the Fourier method
    plot : bool
        Will plot what is removed in the Fourier domain

    Returns
    -------
    list[xr.DataArray] | xr.DataArray
        An object of the same arrays as the input, but modified

    Raises
    ------
    NameError
        If a seasonality removing strategy is not found.
    """
    if isinstance(arrays, xr.DataArray):
        return _remove_seasonality_fourier(arrays.copy(), freq, radius, plot)
    array = arrays[:]
    for i, arr in enumerate(array):
        # Need to re-assign `arr`, otherwise it will be re-used
        array[i] = _remove_seasonality_fourier(arr, freq, radius, plot)
    return array[:]


def _remove_seasonality_fourier(
    arr: xr.DataArray, freq: float, radius: float, plot: bool
) -> xr.DataArray:
    """Remove seasonality via Fourier transform.

    Parameters
    ----------
    arr : xr.DataArray
        An xarray DataArray.
    frequency : float
        Give a custom frequency that should be removed. Default is 1.
    radius : float
        Give a custom radius that should be removed. Default is 0.01.
    plot : bool
        Will plot what is removed in the Fourier domain

    Returns
    -------
    xr.DataArray
        An xarray DataArray.

    Raises
    ------
    TypeError
        If the time axis type is not recognised and we cannot translate to frequency.
    """
    if isinstance(arr.time.data[0], float):
        sample_spacing = arr.time.data[1] - arr.time.data[0]
    elif isinstance(arr.time.data, xr.CFTimeIndex | np.ndarray) and isinstance(
        arr.time.data[0], cftime.datetime
    ):
        sec_in_year = 3600 * 24 * 365
        sample_spacing = (
            arr.time.data[11] - arr.time.data[10]
        ).total_seconds() / sec_in_year
    else:
        raise TypeError(
            f"I cannot handle time arrays where {type(arr.time.data) = } and"
            f" {type(arr.time.data[0]) = }. The array must be a numpy.ndarray or"
            " xr.CFTimeIndex, and the elements must be floats or cftime.datetime."
        )
    n = len(arr.time.data)
    yf = scipy.fft.rfft(arr.data)
    xf = scipy.fft.rfftfreq(n, sample_spacing)
    idx = np.argwhere((xf > freq - radius) & (xf < freq + radius))
    yf_clean = yf.copy()
    if any(idx):
        linear_fill = np.linspace(
            yf_clean[idx[0] - 1], yf_clean[idx[-1] + 1], len(yf_clean[idx])
        )
        yf_clean[idx] = linear_fill
    else:
        print(
            "WARNING: No frequencies were removed! The radius is probably too small,"
            " try with a larger one."
        )
        print(
            "HINT: You can also view the before/after of this function by pasing in"
            " the `plot=True` keyword argument."
        )
    new_f_clean = scipy.fft.irfft(yf_clean)
    if plot:
        plt.semilogy(xf, np.abs(yf))
        plt.semilogy(xf, np.abs(yf_clean))
        plt.xlim([-1, 10])
        plt.show()
    arr.data[: len(new_f_clean)] = new_f_clean

    return arr[:]