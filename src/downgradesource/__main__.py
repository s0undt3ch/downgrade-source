import argparse
import pathlib
import sys
from typing import List
from typing import Optional

import black
from lib3to6 import checker_base as cb
from lib3to6 import checkers
from lib3to6 import common
from lib3to6 import fixer_base as fb
from lib3to6 import fixers
from lib3to6 import transpile


BLACK_TARGET_VERSIONS = {vs.name: vs for vs in black.TargetVersion}


def format_code(contents: str, black_mode: black.FileMode) -> str:
    try:
        formatted_contents: str = black.format_str(contents, mode=black_mode)
        return formatted_contents
    except Exception:
        # We simply ignore any exceptions raised by black and return the
        # unformatted contents
        return contents


def untype_source(
    files: List[pathlib.Path],
    pkg_path: pathlib.Path,
    target_version: str,
    checkers_list: List[str],
    fixers_list: List[str],
    install_requires: List[str],
    skip_black_formatting: bool = False,
) -> int:
    exitcode = 0
    for src_file in files:
        relative = src_file.relative_to(pkg_path)
        destdir = pkg_path / "downgraded"
        destdir.mkdir(parents=True, exist_ok=True)
        destdir.joinpath("__init__.py").touch()
        dest = destdir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            prev_contents = dest.read_text()
        else:
            prev_contents = None
        ctx = common.init_build_context(
            checkers=",".join(checkers_list),
            fixers=",".join(fixers_list),
            target_version=target_version,
            filepath=src_file.name,
            install_requires=" ".join(install_requires).strip() or None,
        )
        source_text = src_file.read_text()
        try:
            fixed_source_text = transpile.transpile_module(ctx, source_text)
        except common.CheckError as err:
            loc = str(src_file)
            if err.lineno >= 0:
                loc += "@" + str(err.lineno)

            err.args = (loc + " - " + err.args[0],) + err.args[1:]
            raise

        if skip_black_formatting is False:
            black_target_version = BLACK_TARGET_VERSIONS.get(
                "PY{}".format(target_version.replace(".", ""))
            )
            if black_target_version:
                target_versions = [black_target_version]
            else:
                target_versions = None
            black_mode = black.FileMode(target_versions=target_versions, string_normalization=False)
            fixed_source_text = format_code(fixed_source_text, black_mode)

        if not prev_contents or prev_contents != fixed_source_text:
            print(f"Untyping {src_file} -> {dest}")
            dest.write_text(fixed_source_text)
            exitcode = 1
    return exitcode


def main(argv: Optional[List[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    checkers_list = list(transpile.get_available_classes(checkers, cb.CheckerBase))
    fixers_list = list(transpile.get_available_classes(fixers, fb.FixerBase))
    parser = argparse.ArgumentParser(prog=__name__)
    parser.add_argument(
        "--target-version",
        default="3.5",
        help="The target version to translate the source code into.",
    )
    parser.add_argument(
        "--pkg-path",
        type=pathlib.Path,
        required=True,
        help="Path to package. For example, `--pkg-source=src/mypackage`",
    )
    parser.add_argument("--list-checkers", action="store_true")
    parser.add_argument(
        "--sc",
        "--skip-checker",
        dest="skip_checkers",
        action="append",
        default=[],
        help="List checkers to skip. Check all of them by passing --list-checkers",
    )
    parser.add_argument("--list-fixers", action="store_true")
    parser.add_argument(
        "--sf",
        "--skip-fixer",
        dest="skip_fixers",
        action="append",
        default=[],
        help="List fixers to skip. Check all of them by passing --list-fixers",
    )
    parser.add_argument(
        "--ir",
        "--install-requires",
        dest="install_requires",
        action="append",
        default=[],
        help=(
            "List of install requirements. This list is passed directly to "
            "lib3to6, the underlying library which does the downgrade "
            "procedure."
        ),
    )
    parser.add_argument(
        "--no-black",
        action="store_true",
        default=False,
        help="Don't format the 'downgraded' code with Black.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=pathlib.Path,
        default=[],
        help="Space separated list of files.",
    )

    options = parser.parse_args(argv)
    if options.list_fixers:
        parser.exit(
            status=0,
            message="Fixers List:\n{}\n".format("\n".join([f"  - {item}" for item in fixers_list])),
        )
    if options.list_checkers:
        parser.exit(
            status=0,
            message="Checkers List:\n{}\n".format(
                "\n".join([f"  - {item}" for item in checkers_list])
            ),
        )

    for checker in options.skip_checkers:
        if checker not in checkers_list:
            parser.exit(
                status=1,
                message=f"{checker} is not a valid checker. Pass --list-checkers for the full allowed list",
            )

    for fixer in options.skip_fixers:
        if fixer not in fixers_list:
            parser.exit(
                status=1,
                message=f"{fixer} is not a valid fixer. Pass --list-fixers for the full allowed list",
            )

    if not options.files:
        parser.exit(status=1, message="No files were passed")

    exitcode = untype_source(
        files=options.files,
        pkg_path=options.pkg_path,
        target_version=options.target_version,
        checkers_list=[ck for ck in checkers_list if ck not in options.skip_checkers],
        fixers_list=[fx for fx in fixers_list if fx not in options.skip_fixers],
        install_requires=options.install_requires,
        skip_black_formatting=options.no_black is True,
    )
    parser.exit(status=exitcode)


if __name__ == "__main__":
    main(sys.argv[1:])
