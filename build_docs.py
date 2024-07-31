import os
import shutil
import subprocess
import sys
from pathlib import Path

REDIRECT_HTML = """
<!DOCTYPE html>
<meta charset="utf-8">
<title>Redirecting...</title>
<meta http-equiv="refresh" content="0; URL=./{}/">
"""
FULL_GITHUB_REPO = sys.argv[1]
split_path = FULL_GITHUB_REPO.split('/',1)
GITHUB_REPO = split_path[1]

current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.abspath(os.path.join(current_script_dir, '..'))
source_dir = os.path.join(project_root_dir, 'docs')

DOCS_BUILD = os.path.join(project_root_dir, "docs/_build/ape_vyper")
DOCS_BUILD_PATH = Path(f"{DOCS_BUILD}")
LATEST_PATH = DOCS_BUILD_PATH / "latest"
STABLE_PATH = DOCS_BUILD_PATH / "stable"


class ApeDocsBuildError(Exception):
    pass

    
def git(*args):
    return subprocess.check_output(["git", *args]).decode("ascii").strip()


def new_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True)
    return path


def build_docs(path: Path) -> Path:
    path = new_dir(path)

    try:
        subprocess.check_call(["sphinx-build", source_dir, str(path), "-c", "sphinx-build"])
    except subprocess.SubprocessError as err:
        raise ApeDocsBuildError(f"Command 'sphinx-build docs {path}' failed.") from err

    return path


def main():
    """
    There are three GH events we build for:

    1. Push to main: we build into 'latest/'.
       The GH action will commit these changes to the 'gh-pages' branch.

    2. Release: we copy 'latest/' into the release dir, as well as to 'stable/'.
       The GH action will commit these changes to the 'gh-pages' branch.

    3. Pull requests or local development: We ensure a successful build.
    """

    event_name = os.environ.get("GITHUB_EVENT_NAME")
    is_ephemeral = event_name in ["pull_request", None]

    if event_name == "push" or is_ephemeral:
        build_docs(LATEST_PATH)
    elif event_name == "release":
        tag = git("describe", "--tag")
        if not tag:
            raise ApeDocsBuildError("Unable to find release tag.")

        if "beta" not in tag and "alpha" not in tag:
            build_dir = DOCS_BUILD_PATH / tag
            build_docs(build_dir)

            # Clean-up unnecessary extra 'fonts/' directories to save space.
            # There should still be one in 'latest/'
            for font_dirs in build_dir.glob("**/fonts"):
                if font_dirs.exists():
                    shutil.rmtree(font_dirs)

            shutil.copytree(build_dir, STABLE_PATH)
        else:
            build_docs(STABLE_PATH)

    # Set up the redirect at /index.html
    DOCS_BUILD_PATH.mkdir(exist_ok=True, parents=True)
    with open(DOCS_BUILD_PATH / "index.html", "w") as f:
        redirect = "latest" if is_ephemeral else "stable"
        f.write(REDIRECT_HTML.format(redirect))


if __name__ == "__main__":
    main()
