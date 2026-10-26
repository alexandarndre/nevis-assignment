from pydantic import BaseModel, JsonValue


class Header(BaseModel):
    name: str
    description: str
    values: list[str]


class SuccessResponse(BaseModel):
    description: str
    example: JsonValue
    headers: list[Header]

    def documented(self) -> dict[int | str, dict[str, JsonValue]]:
        return {
            200: {
                "description": self.description,
                "headers": {
                    header.name: {
                        "description": header.description,
                        "schema": {"type": "string", "enum": [value for value in header.values]},
                    }
                    for header in self.headers
                },
                "content": {"application/json": {"example": self.example}},
            }
        }
