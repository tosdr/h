from unittest import mock

import pytest
from passlib.context import CryptContext

from h import models
from h.cli.commands import user as user_cli
from h.services.annotation_delete import AnnotationDeleteService
from h.services.delete_user import DeleteUserService
from h.services.user_password import UserPasswordService


class TestAddCommand:
    def test_it_adds_user_with_default_authority(self, cli, cliconfig, signup_service):
        result = cli.invoke(
            user_cli.add,
            [
                "--username",
                "admin",
                "--email",
                "admin@localhost",
                "--password",
                "admin",
            ],
            obj=cliconfig,
        )

        assert not result.exit_code

        signup_service.signup.assert_called_with(
            username="admin",
            email="admin@localhost",
            password="admin",
            require_activation=False,
        )

    def test_it_adds_user_with_specific_authority(self, cli, cliconfig, signup_service):
        result = cli.invoke(
            user_cli.add,
            [
                "--username",
                "admin",
                "--email",
                "admin@localhost",
                "--password",
                "admin",
                "--authority",
                "publisher.org",
            ],
            obj=cliconfig,
        )

        assert not result.exit_code

        signup_service.signup.assert_called_with(
            username="admin",
            email="admin@localhost",
            password="admin",
            authority="publisher.org",
            require_activation=False,
        )


class TestAdminCommand:
    def test_it_adds_admin(self, cli, cliconfig, non_admin_user, db_session):
        result = cli.invoke(
            user_cli.admin, ["--on", non_admin_user.username], obj=cliconfig
        )

        assert not result.exit_code

        user = db_session.query(models.User).get(non_admin_user.id)
        assert user.admin

    def test_it_adds_admin_by_default(self, cli, cliconfig, non_admin_user, db_session):
        result = cli.invoke(user_cli.admin, [non_admin_user.username], obj=cliconfig)

        assert not result.exit_code

        user = db_session.query(models.User).get(non_admin_user.id)
        assert user.admin

    def test_it_adds_admin_with_specific_authority(
        self, cli, cliconfig, non_admin_user, db_session
    ):
        non_admin_user.authority = "partner.org"
        db_session.flush()

        result = cli.invoke(
            user_cli.admin,
            ["--authority", "partner.org", non_admin_user.username],
            obj=cliconfig,
        )

        assert not result.exit_code

        user = db_session.query(models.User).get(non_admin_user.id)
        assert user.admin

    def test_it_removes_admin(self, cli, cliconfig, admin_user, db_session):
        result = cli.invoke(
            user_cli.admin, ["--off", admin_user.username], obj=cliconfig
        )

        assert not result.exit_code

        user = db_session.query(models.User).get(admin_user.id)
        assert not user.admin

    def test_it_removes_admin_with_specific_authority(
        self, cli, cliconfig, admin_user, db_session
    ):
        admin_user.authority = "partner.org"

        result = cli.invoke(
            user_cli.admin,
            ["--off", "--authority", "partner.org", admin_user.username],
            obj=cliconfig,
        )

        assert not result.exit_code

        user = db_session.query(models.User).get(admin_user.id)
        assert not user.admin

    def test_it_errors_when_user_could_not_be_found(
        self, cli, cliconfig, non_admin_user, db_session
    ):
        result = cli.invoke(
            user_cli.admin, [f"bogus_{non_admin_user.username}"], obj=cliconfig
        )

        assert result.exit_code == 1
        user = db_session.query(models.User).get(non_admin_user.id)
        assert not user.admin

    def test_it_errors_when_user_with_specific_authority_could_not_be_found(
        self, cli, cliconfig, non_admin_user, db_session
    ):
        result = cli.invoke(
            user_cli.admin,
            ["--authority", "foo.com", non_admin_user.username],
            obj=cliconfig,
        )

        assert result.exit_code == 1
        user = db_session.query(models.User).get(non_admin_user.id)
        assert not user.admin

    @pytest.fixture
    def admin_user(self, db_session, factories):
        return self._user(db_session, factories, True)

    @pytest.fixture
    def non_admin_user(self, db_session, factories):
        return self._user(db_session, factories, False)

    def _user(self, db_session, factories, admin):
        user = factories.User(admin=admin)
        db_session.flush()
        return user


class TestPasswordCommand:
    def test_it_changes_password(
        self, cli, cliconfig, user, db_session, password_service
    ):
        result = cli.invoke(
            user_cli.password, [user.username, "--password", "newpass"], obj=cliconfig
        )

        assert not result.exit_code

        user = db_session.query(models.User).get(user.id)
        assert password_service.check_password(user, "newpass")

    def test_it_changes_password_with_specific_authority(
        self, cli, cliconfig, user, db_session, password_service
    ):
        user.authority = "partner.org"
        db_session.flush()

        result = cli.invoke(
            user_cli.password,
            ["--authority", "partner.org", user.username, "--password", "newpass"],
            obj=cliconfig,
        )

        assert not result.exit_code

        user = db_session.query(models.User).get(user.id)
        assert password_service.check_password(user, "newpass")

    def test_it_errors_when_user_could_not_be_found(
        self, cli, cliconfig, user, db_session, password_service
    ):
        result = cli.invoke(
            user_cli.password,
            [f"bogus_{user.username}", "--password", "newpass"],
            obj=cliconfig,
        )

        assert result.exit_code == 1

        user = db_session.query(models.User).get(user.id)
        assert not password_service.check_password(user, "newpass")

    def test_it_errors_when_user_with_specific_authority_could_not_be_found(
        self, cli, cliconfig, user, db_session, password_service
    ):
        result = cli.invoke(
            user_cli.password,
            ["--authority", "foo.com", user.username, "--password", "newpass"],
            obj=cliconfig,
        )

        assert result.exit_code == 1

        user = db_session.query(models.User).get(user.id)
        assert not password_service.check_password(user, "newpass")

    @pytest.fixture
    def user(self, db_session, factories):
        user = factories.User()
        db_session.flush()
        return user


class TestDeleteUserCommand:
    def test_it_deletes_user(self, cli, cliconfig, user, db_session):
        result = cli.invoke(user_cli.delete, [user.username], obj=cliconfig)

        assert not result.exit_code
        assert not db_session.query(models.User).filter_by(id=user.id).count()

    def test_it_deletes_user_with_specific_authority(
        self, cli, cliconfig, user, db_session
    ):
        user.authority = "partner.org"
        db_session.flush()

        result = cli.invoke(
            user_cli.delete,
            ["--authority", "partner.org", user.username],
            obj=cliconfig,
        )

        assert not result.exit_code
        assert not db_session.query(models.User).filter_by(id=user.id).count()

    def test_it_errors_when_user_could_not_be_found(
        self, cli, cliconfig, user, db_session
    ):
        result = cli.invoke(user_cli.delete, [f"bogus_{user.username}"], obj=cliconfig)

        assert result.exit_code == 1
        assert db_session.query(models.User).filter_by(id=user.id).count() == 1

    def test_it_errors_when_user_with_specific_authority_could_not_be_found(
        self, cli, cliconfig, user, db_session
    ):
        result = cli.invoke(
            user_cli.delete, ["--authority", "foo.com", user.username], obj=cliconfig
        )

        assert result.exit_code == 1
        assert db_session.query(models.User).filter_by(id=user.id).count() == 1

    @pytest.fixture
    def user(self, db_session, factories):
        user = factories.User()
        db_session.flush()
        return user


@pytest.fixture
def signup_service():
    signup_service = mock.Mock(spec_set=["signup"])
    return signup_service


@pytest.fixture
def hasher():
    # Use a much faster hasher for testing purposes. DO NOT use as few as
    # 5 rounds of bcrypt in production code under ANY CIRCUMSTANCES.
    return CryptContext(
        schemes=["bcrypt"],
        bcrypt__ident="2b",
        bcrypt__min_rounds=5,
        bcrypt__max_rounds=5,
    )


@pytest.fixture
def password_service(hasher):
    password_service = UserPasswordService()
    password_service.hasher = hasher
    return password_service


@pytest.fixture
def delete_user_service(pyramid_request, annotation_delete_service):
    return DeleteUserService(pyramid_request, annotation_delete_service)


@pytest.fixture
def annotation_delete_service(pyramid_config):  # pylint:disable=unused-argument
    service = mock.create_autospec(
        AnnotationDeleteService, spec_set=True, instance=True
    )
    return service


@pytest.fixture
def pyramid_config(
    pyramid_config, signup_service, password_service, delete_user_service
):
    pyramid_config.register_service(signup_service, name="user_signup")
    pyramid_config.register_service(password_service, name="user_password")
    pyramid_config.register_service(delete_user_service, name="delete_user")
    return pyramid_config


@pytest.fixture
def cliconfig(pyramid_config, pyramid_request):  # pylint:disable=unused-argument
    pyramid_request.tm = mock.Mock()
    return {"bootstrap": mock.Mock(return_value=pyramid_request)}
