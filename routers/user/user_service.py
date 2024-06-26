import binascii

from models.common.token_payload import TokenPayload
from routers.user.user_repo import UserRepo
from models.user_route_models.user import User, BaseUser
from tools.utils.password_utils import PasswordUtils
from tools.utils.access_token_utils import AccessTokenUtils
from fastapi import Response, HTTPException, status, Request


class UserService:
    def __init__(self) -> None:
        self._repo = UserRepo()
        self.password_utils = PasswordUtils()
        self.access_token_utils = AccessTokenUtils()

    # Helper function to set a new access token in the response
    def set_access_token(self, response: Response, user_id: str, user_role: str) -> None:
        new_access_token = self.access_token_utils.create_access_token(user_id=user_id, user_role=user_role)

        self.access_token_utils.set_access_token_in_cookies(response=response, access_token=new_access_token)

    # Service for checking login details

    def me(self, request: Request) -> TokenPayload:
        token_payload = self.access_token_utils.get_access_token_payload(request=request)
        if token_payload:
            return token_payload
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    async def login_user(self, response: Response, base_user: BaseUser) -> bool:
        user_from_db = await self._repo.find_user_in_database(base_user)

        if user_from_db is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        try:
            is_same_password = await self.password_utils.compare_password(base_user.password, user_from_db.get("password"))
        except (UnicodeDecodeError, binascii.Error):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is not encoded using base64.")
        if not is_same_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password"
            )

        user_id = str(user_from_db.get("_id"))
        user_role = user_from_db.get("role")
        self.set_access_token(response=response, user_id=user_id, user_role=user_role)

        return True

    # Service for registering a new user to the database
    async def register_user(self, response: Response, base_user: BaseUser) -> bool:
        try:
            base_user.password = await self.password_utils.encrypt_base64_password(base_user.password)
        except (UnicodeDecodeError, binascii.Error):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password encoding is not valid.")
        user = User(role="user", **(base_user.model_dump()))
        user_id = await self._repo.create_user_in_database(user)

        user_id = str(user_id)
        user_role = "user"
        self.set_access_token(response=response, user_id=user_id, user_role=user_role)

        return True

    def logout_user(self, response: Response):
        self.access_token_utils.remove_access_token_from_cookies(response)
