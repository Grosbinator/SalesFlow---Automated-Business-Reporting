"""Fenêtre de validation des anomalies (tkinter), ouverte par main.py.

Après le contrôle qualité, s'il reste des anomalies, une fenêtre les liste
et permet pour chacune de modifier la valeur, supprimer la ligne ou la
garder telle quelle. Les calculs ne reprennent qu'une fois la fenêtre
validée ; « Annuler » arrête le pipeline sans rien enregistrer.

Mêmes règles que la console de validation.py (classe Session) : contrôles
relancés après chaque décision, data/raw/ jamais modifié, décisions
ajoutées au journal anomalies/corrections.csv et réappliquées ensuite.

Usage : python src/validation_gui.py   (ou automatiquement par main.py)
"""

import ctypes
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

import validation

FAULT_BACKGROUND = "#fde2e1"
PROBLEM_COLOR = "#b42318"
MUTED_COLOR = "#52514e"


class ValidationWindow:
    """Fenêtre de revue. `result` vaut True (continuer) ou False (annulé)."""

    def __init__(self, root, session):
        self.root = root
        self.session = session
        self.result = None
        self.pending = []
        self.current = None

        root.title("SalesFlow — Validation des anomalies")
        root.protocol("WM_DELETE_WINDOW", self.cancel)
        self._build()
        self.refresh()
        # Taille calculée d'après le contenu (et non fixe) : rien n'est coupé,
        # quelle que soit la mise à l'échelle de l'écran.
        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())

    # ------------------------------------------------------------------
    # Construction de la fenêtre
    # ------------------------------------------------------------------

    def _build(self):
        # Hauteur des lignes du tableau d'après la police : sinon le texte
        # est rogné sur les écrans mis à l'échelle.
        linespace = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        ttk.Style(self.root).configure("Treeview", rowheight=int(linespace * 1.5))

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main, text="Anomalies détectées dans les fichiers sources",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            main,
            text="Traitez les anomalies avant le chargement en base. Les fichiers "
                 "de data/raw/ ne sont jamais modifiés ; chaque décision est "
                 "enregistrée dans anomalies/corrections.csv.",
            foreground=MUTED_COLOR, wraplength=940,
        ).pack(anchor="w", pady=(2, 10))

        body = ttk.Panedwindow(main, orient="horizontal")
        body.pack(fill="both", expand=True)

        # Liste des anomalies restantes (à gauche).
        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        self.count_label = ttk.Label(left, font=("Segoe UI", 10, "bold"))
        self.count_label.pack(anchor="w", pady=(0, 4))
        self.listbox = tk.Listbox(
            left, width=40, height=14, activestyle="none", exportselection=False,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(left, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        body.add(left, weight=1)

        # Détail de l'anomalie sélectionnée (à droite).
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        self.header = ttk.Label(right, font=("Segoe UI", 11, "bold"))
        self.header.pack(anchor="w")
        self.problem = ttk.Label(right, foreground=PROBLEM_COLOR, wraplength=480)
        self.problem.pack(anchor="w", pady=(2, 8))

        self.row_view = ttk.Treeview(
            right, columns=("column", "value"), show="headings", height=8,
        )
        self.row_view.heading("column", text="Colonne")
        self.row_view.heading("value", text="Valeur")
        self.row_view.column("column", width=150, stretch=False)
        self.row_view.tag_configure("fault", background=FAULT_BACKGROUND)
        self.row_view.pack(fill="x")

        edit = ttk.Frame(right)
        edit.pack(fill="x", pady=(10, 4))
        self.edit_label = ttk.Label(edit, text="Nouvelle valeur :")
        self.edit_label.pack(side="left")
        self.value_var = tk.StringVar()
        self.entry = ttk.Entry(edit, textvariable=self.value_var, width=28)
        self.entry.pack(side="left", padx=6)
        self.entry.bind("<Return>", lambda _event: self.modify())
        self.modify_button = ttk.Button(edit, text="Modifier", command=self.modify)
        self.modify_button.pack(side="left")

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=4)
        self.delete_button = ttk.Button(
            actions, text="Supprimer la ligne", command=self.delete,
        )
        self.delete_button.pack(side="left")
        self.keep_button = ttk.Button(
            actions, text="Garder tel quel", command=self.keep,
        )
        self.keep_button.pack(side="left", padx=6)

        self.status = ttk.Label(right, foreground=MUTED_COLOR, wraplength=480)
        self.status.pack(anchor="w", pady=(8, 0))
        body.add(right, weight=2)

        footer = ttk.Frame(main)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(
            footer, text="Enregistrer et continuer", command=self.finish,
        ).pack(side="right")
        ttk.Button(
            footer, text="Annuler", command=self.cancel,
        ).pack(side="right", padx=6)

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------

    def refresh(self, select_index=0):
        """Relance les contrôles et met à jour la liste et le détail."""
        self.pending = self.session.pending()
        self.listbox.delete(0, "end")
        for anomaly in self.pending:
            # Message complet affiché à droite : la liste reste étroite.
            self.listbox.insert(
                "end",
                f"{anomaly['file_name']} · ligne {anomaly['row_number']} · "
                f"{anomaly['column_name']}",
            )
        self.count_label.config(text=f"{len(self.pending)} anomalie(s) restante(s)")

        if not self.pending:
            self.current = None
            self.header.config(text="Toutes les anomalies sont traitées.")
            self.problem.config(text="Cliquez sur « Enregistrer et continuer ».")
            self.row_view.delete(*self.row_view.get_children())
            self.value_var.set("")
            for widget in (self.entry, self.modify_button,
                           self.delete_button, self.keep_button):
                widget.state(["disabled"])
            return

        index = min(select_index, len(self.pending) - 1)
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        self.listbox.see(index)
        self.show(self.pending[index])

    def show(self, anomaly):
        """Affiche une anomalie et la ligne complète du CSV."""
        self.current = anomaly
        column = anomaly["column_name"]
        self.header.config(
            text=f"{anomaly['file_name']} — ligne {anomaly['row_number']} — "
                 f"colonne {column}"
        )
        self.problem.config(text=f"Problème : {anomaly['error_message']}")

        self.row_view.delete(*self.row_view.get_children())
        row = self.session.frames[anomaly["file_name"]].loc[
            validation.row_index(anomaly)
        ]
        for name, value in row.items():
            self.row_view.insert(
                "", "end", values=(name, value if value != "" else "(vide)"),
                tags=("fault",) if name == column else (),
            )

        self.edit_label.config(text=f"Nouvelle valeur pour {column} :")
        self.value_var.set(self.session.value(anomaly))
        for widget in (self.entry, self.modify_button, self.delete_button):
            widget.state(["!disabled"])
        # « Garder » seulement si l'anomalie ne bloque pas le chargement en base.
        self.keep_button.state(
            ["!disabled"] if validation.can_keep(anomaly) else ["disabled"]
        )
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def on_select(self, _event=None):
        selection = self.listbox.curselection()
        if selection:
            self.show(self.pending[selection[0]])

    def current_position(self):
        return self.pending.index(self.current) if self.current in self.pending else 0

    # ------------------------------------------------------------------
    # Décisions
    # ------------------------------------------------------------------

    def modify(self):
        if self.current is None:
            return
        position = self.current_position()
        column = self.current["column_name"]
        old_value = self.session.value(self.current)
        new_value = self.value_var.get().strip()

        if new_value == old_value:
            self.status.config(text="Valeur inchangée : saisissez une nouvelle valeur.")
            return
        if new_value == "" and not messagebox.askyesno(
            "Vider la cellule", f"Laisser {column} vide ?", parent=self.root,
        ):
            return

        self.session.modify(self.current, new_value)
        self.status.config(
            text=f"{column} : {old_value or '(vide)'} -> {new_value or '(vide)'}"
        )
        # Si la nouvelle valeur est encore fausse, l'anomalie reste à cette place.
        self.refresh(position)

    def delete(self):
        if self.current is None:
            return
        anomaly = self.current
        if not messagebox.askyesno(
            "Supprimer la ligne",
            f"Supprimer la ligne {anomaly['row_number']} de "
            f"{anomaly['file_name']} des données nettoyées ?",
            parent=self.root,
        ):
            return
        position = self.current_position()
        self.session.delete(anomaly)
        self.status.config(
            text=f"Ligne {anomaly['row_number']} de {anomaly['file_name']} supprimée."
        )
        self.refresh(position)

    def keep(self):
        if self.current is None or not validation.can_keep(self.current):
            return
        position = self.current_position()
        self.session.keep(self.current)
        self.status.config(text="Valeur gardée telle quelle.")
        self.refresh(position)

    def finish(self):
        remaining = len(self.pending)
        if remaining and not messagebox.askyesno(
            "Anomalies restantes",
            f"{remaining} anomalie(s) non traitée(s) : les lignes concernées "
            "seront écartées des données nettoyées.\n\nContinuer ?",
            parent=self.root,
        ):
            return
        self.result = True
        self.root.destroy()

    def cancel(self):
        if messagebox.askyesno(
            "Annuler",
            "Arrêter le pipeline ? Les décisions prises dans cette fenêtre "
            "ne seront pas enregistrées.",
            parent=self.root,
        ):
            self.result = False
            self.root.destroy()


def enable_high_dpi():
    """Texte net sur les écrans Windows mis à l'échelle (125 %, 150 %...)."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass  # anciennes versions de Windows : affichage par défaut


def bring_to_front(root):
    """Affiche la fenêtre au premier plan (elle s'ouvre depuis un terminal)."""
    root.lift()
    root.attributes("-topmost", True)
    root.after(500, lambda: root.attributes("-topmost", False))
    root.focus_force()


def gui_validate(show=print):
    """Validation avec fenêtre (utilisée par main.py).

    Réapplique le journal ; s'il reste des anomalies, ouvre la fenêtre.
    Enregistre ensuite data/processed/ (lignes non traitées écartées).
    Renvoie True si les données ont été enregistrées, False si annulé.
    Lève tk.TclError si aucun affichage n'est disponible.
    """
    frames = validation.load_frames()
    kept, applied = validation.replay(frames, validation.load_journal())
    if applied:
        show(f"{applied} décision(s) du journal réappliquée(s).")
    session = validation.Session(frames, kept)

    if not session.pending():
        show("Aucune anomalie à traiter.")
    else:
        show(f"{len(session.pending())} anomalie(s) à traiter : "
             "fenêtre de validation ouverte.")
        enable_high_dpi()
        root = tk.Tk()
        window = ValidationWindow(root, session)
        bring_to_front(root)
        root.mainloop()
        if not window.result:
            show("Validation annulée : rien n'a été enregistré.")
            return False

    excluded = validation.exclude_unresolved(frames, session.kept)
    validation.save(frames, session.log + excluded)
    show(f"{len(session.log)} décision(s) enregistrée(s), "
         f"{len(excluded)} anomalie(s) non traitée(s) : lignes écartées.")
    validation.show_counts(frames, show)
    return True


if __name__ == "__main__":
    gui_validate()
