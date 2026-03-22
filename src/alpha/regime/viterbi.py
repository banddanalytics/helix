"""Offline log-space Viterbi decoding for HMM-GARCH regime detector."""

from __future__ import annotations

import numpy as np


def viterbi_decode(
    log_emission_probs: np.ndarray,
    log_transmat: np.ndarray,
    log_startprob: np.ndarray,
) -> np.ndarray:
    """Viterbi algorithm in log-space (no numerical underflow).

    Finds the optimal state sequence given observed log-emission probabilities,
    a log-transition matrix, and log-initial-state probabilities.

    Parameters
    ----------
    log_emission_probs : np.ndarray, shape (T, n_states)
        Log-emission log-probabilities for each time step and state.
    log_transmat : np.ndarray, shape (n_states, n_states)
        Log-transition matrix where log_transmat[i, j] = log P(s_t=j | s_{t-1}=i).
    log_startprob : np.ndarray, shape (n_states,)
        Log-initial-state probabilities.

    Returns
    -------
    states : np.ndarray, shape (T,), dtype int64
        Optimal (most probable) state sequence.
    """
    T, n_states = log_emission_probs.shape

    # delta[t, j] = log probability of the most probable path ending in state j at time t
    delta = np.empty((T, n_states), dtype=np.float64)
    # psi[t, j] = best predecessor state at time t-1 for state j at time t
    psi = np.empty((T, n_states), dtype=np.int64)

    # Initialisation
    delta[0] = log_startprob + log_emission_probs[0]
    psi[0] = 0  # no predecessor at t=0

    # Forward pass
    for t in range(1, T):
        # For each state j, find best predecessor i
        # scores[i, j] = delta[t-1, i] + log_transmat[i, j]
        scores = delta[t - 1, :, np.newaxis] + log_transmat  # (n_states, n_states)
        psi[t] = np.argmax(scores, axis=0)
        delta[t] = scores[psi[t], np.arange(n_states)] + log_emission_probs[t]

    # Backtrack
    states = np.empty(T, dtype=np.int64)
    states[T - 1] = int(np.argmax(delta[T - 1]))
    for t in range(T - 2, -1, -1):
        states[t] = psi[t + 1, states[t + 1]]

    return states


__all__ = ["viterbi_decode"]
