from __future__ import annotations

from textual.containers import Vertical


class Pane(Vertical):
    """Base class for a dashboard pane that fetches and renders its own data.

    Subclasses implement :meth:`_fetch` (HTTP / I/O) and :meth:`_on_data`
    (update widgets).  The public :meth:`fetch` and :meth:`refresh_now`
    methods provide the right threading semantics for the two call-sites:

    * ``fetch()``      — called from a background thread (periodic poll);
                        implementations should use ``self.call_later(self._on_data)``.
    * ``refresh_now()`` — called from the UI thread (e.g. after a model change);
                        ``_on_data`` runs synchronously.
    """

    def fetch(self) -> None:
        """Fetch data and schedule render (periodic poll / mount)."""
        self._fetch()

    def refresh_now(self) -> None:
        """Synchronous re-fetch + immediate render (child-triggered refresh)."""
        self._fetch()
        self._on_data()

    def _fetch(self) -> None:
        raise NotImplementedError

    def _on_data(self) -> None:
        raise NotImplementedError
