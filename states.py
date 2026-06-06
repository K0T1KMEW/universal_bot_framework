from typing import Union, Optional
from .storage import BaseStorage

class State:
    def __init__(self, name: str):
        self.name = name

class StatesGroupMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        states = {}
        for key, value in attrs.items():
            if isinstance(value, State):
                states[key] = value
                setattr(cls, key, value)
        cls._states = states
        return cls

class StatesGroup(metaclass=StatesGroupMeta):
    pass