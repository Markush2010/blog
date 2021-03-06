import sys
from functools import wraps

from fabric import task

hosts = ["kamp1.markusholtermann.eu"]


def verify_remote(func):
    @wraps(func)
    def wrapper(c):
        if c.config.deploy_dir is None:
            print("No deploy_dir specified")
            sys.exit(1)
        if c.config.repo_dir is None:
            print("No repo_dir specified")
            sys.exit(2)
        if c.config.venv_dir is None:
            print("No venv_dir specified")
            sys.exit(4)
        func(c)

    return wrapper


@task(hosts=hosts)
@verify_remote
def bootstrap(c):
    """
    Remote -- Bootstrap git repo, virtualenv, sass, grunt
    """
    c.run(f"mkdir -p {c.config.repo_dir}")
    with c.cd(c.config.repo_dir):
        c.run(f"git clone {c.config.repository} .", warn=True)
        c.run(f"git checkout {c.config.branch}")
        c.run(f"virtualenv {c.config.venv_dir}", warn=True)
        c.run("gem install --user-install sass:3.7.4")
    git(c)
    update(c)


@task(hosts=hosts)
@verify_remote
def git(c):
    """
    Remote -- Installs and updates all requirements.
    """
    with c.cd(c.config.repo_dir):
        c.run(f"git checkout -f {c.config.branch}")
        c.run(f"git pull origin {c.config.branch}")
        c.run("git submodule init")
        c.run("git submodule update")


@task(hosts=hosts)
@verify_remote
def update(c):
    """
    Remote -- Installs and updates all requirements.
    """
    with c.cd(c.config.repo_dir):
        with c.prefix(f"source {c.config.venv_dir}bin/activate"):
            c.run("pip install -r requirements.txt")
            c.run("npm install")


@task(hosts=hosts)
@verify_remote
def grunt_remote(c):
    """
    Remote -- Runs Grunt
    """
    with c.cd(c.config.repo_dir):
        c.run("make grunt")


@task(hosts=hosts)
@verify_remote
def pelican_remote(c):
    """
    Remote -- Runs Pelican
    """
    with c.cd(c.config.repo_dir):
        with c.prefix(f"source {c.config.venv_dir}bin/activate"):
            c.run(f"make pelican -e PELICAN_SETTINGS={c.config.pelicanconf}")


@task(hosts=hosts)
@verify_remote
def build_remote(c):
    """
    Remote -- Deploys the latest changes: grunt-remote, pelican-remote
    """
    grunt_remote(c)
    pelican_remote(c)


@task(hosts=hosts)
@verify_remote
def rsync(c):
    """
    Remote -- Rsync
    """
    with c.cd(c.config.repo_dir):
        c.run(f"rsync -av --checksum ./build/ {c.config.deploy_dir}")


@task(hosts=hosts)
@verify_remote
def deploy(c):
    """
    Remote -- Do everything needed to deploy: git, update, build-remote, rsync
    """
    git(c)
    update(c)
    build_remote(c)
    rsync(c)
