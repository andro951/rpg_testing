"""Synthetic output fixtures; never real model inference."""
from prompt_builder.reference_output import encode

def encode_response(case,form):
    return encode(case['starting_data'],case['expected_patch'],form)
