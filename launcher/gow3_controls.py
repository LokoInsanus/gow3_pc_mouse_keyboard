# SPDX-License-Identifier: GPL-2.0-or-later
"""Remapeamento de controles do gow3_launcher_win.py (Tkinter).

Portado do bbport_launcher.py: o botao "Atribuir" espera a proxima tecla (teclado) ou
o proximo botao (gamepad) e grava o resultado; "Resetar" volta ao padrao.

No bbport isso e feito pelo binario nativo `bb-gpu-capabilities --read-input`; aqui a captura
e feita direto em Python, sem dependencias:
  * teclado: evento <KeyPress> do Tk;
  * gamepad: XInput (xinput1_4.dll via ctypes, Windows; controles Xbox/XInput).
Os nomes gravados seguem o bbport (teclas: "Space", "Left Shift"...; botoes: nomes SDL).
"""
import sys
import tkinter as tk
from tkinter import ttk

WINDOWS = sys.platform == 'win32'

# (entrada, rotulo, tecla padrao, botao padrao do gamepad ou None = sem atribuicao de gamepad)
CONTROLS = [
    ('cross', 'Cross (X)', 'Space', 'a'),
    ('circle', 'Circle', 'Left Shift', 'b'),
    ('square', 'Square', 'E', 'x'),
    ('triangle', 'Triangle', 'Q', 'y'),
    ('l1', 'L1', '1', 'leftshoulder'),
    ('r1', 'R1', '3', 'rightshoulder'),
    ('l2', 'L2', 'R', 'lefttrigger'),
    ('r2', 'R2', 'F', 'righttrigger'),
    ('l3', 'L3', 'Z', 'leftstick'),
    ('r3', 'R3', 'C', 'rightstick'),
    ('options', 'Options', 'Return', 'start'),
    ('touchpad', 'Touchpad', 'Tab', 'back'),
    ('up', 'D-pad cima', 'I', 'dpup'),
    ('down', 'D-pad baixo', 'K', 'dpdown'),
    ('left', 'D-pad esquerda', 'J', 'dpleft'),
    ('right', 'D-pad direita', 'L', 'dpright'),
    ('move_up', 'Mover para frente', 'W', None),
    ('move_down', 'Mover para tras', 'S', None),
    ('move_left', 'Mover para esquerda', 'A', None),
    ('move_right', 'Mover para direita', 'D', None),
    ('look_up', 'Camera cima', 'Up', None),
    ('look_down', 'Camera baixo', 'Down', None),
    ('look_left', 'Camera esquerda', 'Left', None),
    ('look_right', 'Camera direita', 'Right', None),
]

# keysym do Tk -> nome gravado no .ini
KEYSYM_NAMES = {
    'space': 'Space', 'Return': 'Return', 'Tab': 'Tab', 'BackSpace': 'Backspace',
    'Shift_L': 'Left Shift', 'Shift_R': 'Right Shift',
    'Control_L': 'Left Ctrl', 'Control_R': 'Right Ctrl',
    'Alt_L': 'Left Alt', 'Alt_R': 'Right Alt',
    'Up': 'Up', 'Down': 'Down', 'Left': 'Left', 'Right': 'Right',
    'Prior': 'PageUp', 'Next': 'PageDown', 'Home': 'Home', 'End': 'End',
    'Insert': 'Insert', 'Delete': 'Delete', 'Caps_Lock': 'CapsLock',
}


def key_name(event):
    sym = event.keysym
    if sym in KEYSYM_NAMES:
        return KEYSYM_NAMES[sym]
    if len(sym) == 1:
        return sym.upper()
    if sym.startswith('KP_'):
        return 'Keypad ' + sym[3:]
    return sym  # F1..F12 e demais


# --- Gamepad via XInput (Windows) ------------------------------------------------------------

XINPUT_BUTTONS = [  # mascara de wButtons -> nome SDL
    (0x0001, 'dpup'), (0x0002, 'dpdown'), (0x0004, 'dpleft'), (0x0008, 'dpright'),
    (0x0010, 'start'), (0x0020, 'back'), (0x0040, 'leftstick'), (0x0080, 'rightstick'),
    (0x0100, 'leftshoulder'), (0x0200, 'rightshoulder'),
    (0x1000, 'a'), (0x2000, 'b'), (0x4000, 'x'), (0x8000, 'y'),
]
TRIGGER_THRESHOLD = 128


class XInputReader:
    """Le o estado dos controles XInput (ate 4). Sem XInput/Linux: available == False."""

    def __init__(self):
        self.available = False
        if not WINDOWS:
            return
        import ctypes

        class Gamepad(ctypes.Structure):
            _fields_ = [('wButtons', ctypes.c_ushort), ('bLeftTrigger', ctypes.c_ubyte),
                        ('bRightTrigger', ctypes.c_ubyte), ('sThumbLX', ctypes.c_short),
                        ('sThumbLY', ctypes.c_short), ('sThumbRX', ctypes.c_short),
                        ('sThumbRY', ctypes.c_short)]

        class State(ctypes.Structure):
            _fields_ = [('dwPacketNumber', ctypes.c_ulong), ('Gamepad', Gamepad)]

        self._State = State
        self._ctypes = ctypes
        for dll in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
            try:
                self._get_state = getattr(ctypes.windll, dll).XInputGetState
                self.available = True
                break
            except (OSError, AttributeError):
                continue

    def pressed(self):
        """Conjunto de nomes SDL pressionados agora, em todos os controles conectados."""
        names = set()
        if not self.available:
            return names
        for index in range(4):
            state = self._State()
            if self._get_state(index, self._ctypes.byref(state)) != 0:  # 0 = conectado
                continue
            pad = state.Gamepad
            names.update(name for mask, name in XINPUT_BUTTONS if pad.wButtons & mask)
            if pad.bLeftTrigger >= TRIGGER_THRESHOLD:
                names.add('lefttrigger')
            if pad.bRightTrigger >= TRIGGER_THRESHOLD:
                names.add('righttrigger')
        return names


# --- Interface -------------------------------------------------------------------------------

class ControlsFrame(ttk.Frame):
    """Duas secoes (Teclado / Gamepad) com uma linha por controle: Atribuir e Resetar.

    get_binding(chave) -> str | None   (chave = 'key.cross' / 'pad.cross'; None = padrao)
    set_binding(chave, valor | None)   (grava no gow3.ini / settings; None remove a chave)
    """

    def __init__(self, master, get_binding, set_binding, notify=None):
        super().__init__(master)
        self.get_binding, self.set_binding = get_binding, set_binding
        self.notify = notify or (lambda text: None)  # ex.: texto na barra de status
        self.xinput = XInputReader()
        self.rows = {}        # (kind, name) -> (Label do valor, padrao)
        self.listening = None  # (kind, name) em captura
        self._poll_id = None
        self._baseline = set()
        for column, (kind, title) in enumerate((('key', 'Teclado'), ('pad', 'Gamepad'))):
            box = ttk.LabelFrame(self, text=title, padding=6)
            box.grid(row=0, column=column, sticky='nsew', padx=4, pady=4)
            self.columnconfigure(column, weight=1)
            box.columnconfigure(1, weight=1)
            line = 0
            for name, label, key_default, pad_default in CONTROLS:
                default = key_default if kind == 'key' else pad_default
                if default is None:
                    continue
                ttk.Label(box, text=label).grid(row=line, column=0, sticky='w', pady=1)
                value = ttk.Label(box, width=18, anchor='w')
                value.grid(row=line, column=1, sticky='w', padx=6)
                ttk.Button(box, text='Atribuir', width=8,
                           command=lambda k=kind, n=name: self.assign(k, n)).grid(row=line, column=2)
                ttk.Button(box, text='Resetar', width=8,
                           command=lambda k=kind, n=name: self.reset(k, n)).grid(row=line, column=3, padx=(2, 0))
                self.rows[(kind, name)] = (value, default)
                self.show(kind, name)
                line += 1

    # exibicao
    def show(self, kind, name):
        value, default = self.rows[(kind, name)]
        saved = self.get_binding(f'{kind}.{name}')
        if saved is None:
            value.config(text=f'{default} (padrao)' if default else 'nao atribuido')
        else:
            value.config(text=saved or 'nao atribuido')

    def set_control(self, kind, name, binding):
        self.set_binding(f'{kind}.{name}', binding)
        self.show(kind, name)

    def reset(self, kind, name):
        self.cancel()
        self.set_control(kind, name, None)

    # captura
    def assign(self, kind, name):
        self.cancel()
        if kind == 'pad' and not self.xinput.available:
            self.notify('Captura de gamepad indisponivel (precisa de XInput no Windows).')
            return
        self.listening = (kind, name)
        self.rows[(kind, name)][0].config(text='Pressione... (Esc cancela)')
        self.winfo_toplevel().focus_force()
        self._bind_id = self.winfo_toplevel().bind('<KeyPress>', self._on_key, add='+')
        if kind == 'pad':
            self._baseline = self.xinput.pressed()  # ignora o que ja estava pressionado
            self._poll_id = self.after(30, self._poll_pad)

    def _on_key(self, event):
        if not self.listening:
            return
        kind, name = self.listening
        if event.keysym == 'Escape':
            self.cancel()
        elif kind == 'key':
            self.finish(key_name(event))
        return 'break'

    def _poll_pad(self):
        if not self.listening or self.listening[0] != 'pad':
            return
        now = self.xinput.pressed()
        self._baseline &= now  # soltou: passa a contar como novo se pressionar de novo
        fresh = now - self._baseline
        if fresh:
            self.finish(sorted(fresh)[0])
        else:
            self._poll_id = self.after(30, self._poll_pad)

    def finish(self, binding):
        kind, name = self.listening
        self.stop_listening()
        self.set_control(kind, name, binding)

    def cancel(self):
        if self.listening:
            kind, name = self.listening
            self.stop_listening()
            self.show(kind, name)

    def stop_listening(self):
        self.listening = None
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        try:
            self.winfo_toplevel().unbind('<KeyPress>', self._bind_id)
        except (tk.TclError, AttributeError):
            pass
