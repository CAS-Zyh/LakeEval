import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from ui.theme import apply_theme
from ui.auth import require_role
from ui.components.chat_widget import render_chat_widget

apply_theme()
user = require_role(["admin", "user", "guest"])

render_chat_widget()
