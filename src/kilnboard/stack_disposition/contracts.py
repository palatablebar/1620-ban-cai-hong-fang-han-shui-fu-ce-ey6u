from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Statement:
    identifier: str
    model: str
    source: str
    payload: dict
    state: str


@dataclass(frozen=True, slots=True)
class Publication:
    revision: int
    identifier: str
    replay: bool
    current_revision: int

    def wire(self) -> dict:
        return {'revision':self.revision,'id':self.identifier,'replay':self.replay,
                'current_revision':self.current_revision}


class StalePublication(ValueError):
    def __init__(self, expected: int, actual: int):
        super().__init__('最新派工已变更，请重新预览后发布')
        self.expected = expected
        self.actual = actual


class PublicationBlocked(ValueError):
    """The validation gate has not approved the prepared release."""
