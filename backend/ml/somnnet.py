"""Pure-NumPy CPU inference for the supplied SomnNET binary SpO2 model.

Architecture reproduced from Binary_spo2.ipynb cell [10] and verified against the
tensors in best_weights_spo2_32layer_binary.hdf5:

  input (88,1)
  BatchNormalization(1)
  BinaryConv1D(6,  k=25, same, no bias) -> ReLU
  BinaryConv1D(50, k=10, same, no bias) -> MaxPool(2) -> ReLU
  BinaryConv1D(30, k=15, same, no bias) -> MaxPool(2) -> ReLU
  BatchNormalization(30) -> Flatten (660) -> Dropout(inactive) -> BinaryDense(2, no bias) -> softmax

Binarization: the supplied file stores kernels that are already exactly +/-1 with H=1
(binarize(W)=H*binary_tanh(W/H) is the identity on such values), so the forward pass is a plain
convolution with those +/-1 kernels. The loader *applies binarize anyway* (sign, 0 -> -1, as in
binary_ops.binary_tanh with K.round half-to-even) so a non-binarized checkpoint would behave as in Keras.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from . import config as C

_EXPECTED = {
    "batch_normalization": ("beta", "gamma", "moving_mean", "moving_variance"),
    "batch_normalization_1": ("beta", "gamma", "moving_mean", "moving_variance"),
}
_SHAPES = {"conv1": (25, 1, 6), "conv2": (10, 6, 50), "conv3": (15, 50, 30), "dense1": (660, 2)}


def _read_weights(path: Path) -> dict[str, np.ndarray]:
    flat: dict[str, np.ndarray] = {}
    try:
        import h5py  # preferred
        with h5py.File(str(path), "r") as f:
            def visit(name, obj):
                if isinstance(obj, h5py.Dataset):
                    flat["/" + name] = np.asarray(obj[()], dtype=np.float32)
            f.visititems(visit)
    except ImportError:  # sandbox/CI without h5py: tiny reader that supports this exact file layout
        from ._h5_fallback import H5
        flat = {k: v.astype(np.float32) for k, v in H5(str(path)).datasets.items()}
    out = {}
    for k, v in flat.items():
        parts = k.strip("/").split("/")
        out[f"{parts[0]}/{parts[-1].split(':')[0]}"] = v
    return out


def _binarize(w: np.ndarray, H: float = 1.0) -> np.ndarray:
    hs = np.clip(0.5 * (w / H) + 0.5, 0.0, 1.0)
    return H * (2.0 * np.round(hs) - 1.0)  # np.round is half-to-even, same as K.round


def _conv1d_same(x: np.ndarray, k: np.ndarray) -> np.ndarray:
    n, length, cin = x.shape
    ks, kin, cout = k.shape
    assert kin == cin
    total = ks - 1
    left = total // 2  # TensorFlow 'same' padding: extra pad goes to the right
    xp = np.pad(x, ((0, 0), (left, total - left), (0, 0)))
    win = sliding_window_view(xp, ks, axis=1)            # (n, L, cin, ks)
    return np.einsum("nlck,kco->nlo", win, k, optimize=True)


def _maxpool2(x: np.ndarray) -> np.ndarray:
    L = (x.shape[1] // 2) * 2
    return x[:, :L].reshape(x.shape[0], L // 2, 2, x.shape[2]).max(axis=2)


class SomnNet:
    def __init__(self, weights_path: Path):
        w = _read_weights(Path(weights_path))
        need = [f"{l}/kernel" for l in _SHAPES] + [f"{b}/{p}" for b, ps in _EXPECTED.items() for p in ps]
        missing = [n for n in need if n not in w]
        if missing:
            raise ValueError(f"Weights file does not match the SomnNET architecture; missing tensors: {missing}")
        for layer, shape in _SHAPES.items():
            if w[f"{layer}/kernel"].shape != shape:
                raise ValueError(f"{layer}/kernel has shape {w[f'{layer}/kernel'].shape}, expected {shape}")
        self.k = {l: _binarize(w[f"{l}/kernel"]) for l in _SHAPES}
        self.bn = {b: {p: w[f"{b}/{p}"] for p in ps} for b, ps in _EXPECTED.items()}
        self.weights_path = Path(weights_path)

    @staticmethod
    def _bn(x, p):
        return (x - p["moving_mean"]) / np.sqrt(p["moving_variance"] + C.BN_EPSILON) * p["gamma"] + p["beta"]

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """x: (N, 88) or (N, 88, 1) already normalised. Returns (N, 2) softmax probabilities."""
        x = np.asarray(x, dtype=np.float32)
        if x.ndim == 2:
            x = x[:, :, None]
        if x.ndim != 3 or x.shape[1] != C.WINDOW_SAMPLES or x.shape[2] != 1:
            raise ValueError(f"Model expects windows of shape (N, {C.WINDOW_SAMPLES}, 1); got {x.shape}")
        h = self._bn(x, self.bn["batch_normalization"])
        h = np.maximum(_conv1d_same(h, self.k["conv1"]), 0)
        h = np.maximum(_maxpool2(_conv1d_same(h, self.k["conv2"])), 0)
        h = np.maximum(_maxpool2(_conv1d_same(h, self.k["conv3"])), 0)
        h = self._bn(h, self.bn["batch_normalization_1"])
        z = h.reshape(h.shape[0], -1) @ self.k["dense1"]
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return (e / e.sum(axis=1, keepdims=True)).astype(np.float32)


_MODEL: SomnNet | None = None


def get_model(weights_path: Path) -> SomnNet:
    global _MODEL
    if _MODEL is None or _MODEL.weights_path != Path(weights_path):
        _MODEL = SomnNet(weights_path)
    return _MODEL
