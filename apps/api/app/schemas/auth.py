from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

from app.schemas.user import UserRead


class LoginRequest(SQLModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class RegisterRequest(SQLModel):
    display_name: str
    email: EmailStr

    # `pattern` and not only the validator below, because a field_validator does
    # not become JSON Schema. Until r80 the contract said `minLength: 8` and
    # nothing else, so the registration form generated from it had no uppercase
    # rule to check: an all-lowercase password was accepted by the form, refused
    # on submit, and carried no field-level message -- the shape AI-2 reported on
    # 8 September.
    #
    # It goes in through `schema_extra` rather than a constraint keyword, and
    # both alternatives were tried first: `Field` here is SQLModel's, so
    # `pattern=` is a TypeError, and its `regex=` is a pydantic-v1 shim that is
    # accepted and then dropped -- the generated schema came back with no
    # `pattern` key at all. `schema_extra` reaches the JSON Schema, which is the
    # only thing the frontend reads.
    #
    # Declaring it here also makes pydantic enforce it, and a constraint fires
    # before a plain validator -- which replaced the readable message with
    # "String should match pattern '.*[A-Z].*'". The validator below therefore
    # runs in `before` mode, so the sentence a human reads is still the one that
    # comes back. The expression carries no lookahead, so that whatever regex
    # engine the client uses can compile it.
    password: str = Field(
        ...,
        min_length=8,
        schema_extra={"pattern": r".*[A-Z].*"},
        description=(
            "At least 8 characters and at least 1 uppercase letter. Both rules are "
            "in the contract, so the client can check them before submitting."
        ),
    )

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        # `before`, so this runs ahead of the min_length and pattern constraints
        # and owns the message for the uppercase rule.
        if not isinstance(value, str):
            return value
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least 1 uppercase letter")
        return value.strip()


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
