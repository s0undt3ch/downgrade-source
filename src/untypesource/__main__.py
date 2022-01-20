import argparse
import pathlib
import sys
from typing import List

from lib3to6 import checker_base as cb
from lib3to6 import checkers
from lib3to6 import common
from lib3to6 import fixer_base as fb
from lib3to6 import fixers
from lib3to6 import transpile


def untype_source(
    files: List[pathlib.Path],
    pkg_path: pathlib.Path,
    target_version: str,
    checkers_list: List[str],
    fixers_list: List[str],
) -> int:
    exitcode = 0
    for src_file in files:
        relative = src_file.relative_to(pkg_path)
        dest = pkg_path / "untyped" / relative
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

        if not prev_contents or prev_contents != fixed_source_text:
            print(f"Untyping {src_file} -> {dest}")
            dest.write_text(fixed_source_text)
            exitcode = 1
    return exitcode


def main(argv: List[str] = sys.argv[:1]) -> None:
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
        help="Path to package. For example, `--pkg-source=src/mypackage`",
    )
    parser.add_argument(
        "--sc",
        "--skip-checker",
        dest="skip_checkers",
        action="append",
        default=[],
        choices=checkers_list,
        help="List checkers to skip. One of: {}".format(", ".join(checkers_list)),
    )
    parser.add_argument(
        "--sf",
        "--skip-fixer",
        dest="skip_fixers",
        action="append",
        default=[],
        choices=fixers_list,
        help="List fixers to skip. One of: {}".format(", ".join(fixers_list)),
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=pathlib.Path,
        default=[],
        help="Space separated list of files.",
    )

    options = parser.parse_args(argv)
    exitcode = untype_source(
        files=options.files,
        pkg_path=options.pkg_path,
        target_version=options.target_version,
        checkers_list=[ck for ck in checkers_list if ck not in options.skip_checkers],
        fixers_list=[fx for fx in fixers_list if fx not in options.skip_fixers],
    )
    parser.exit(status=exitcode)


if __name__ == "__main__":
    main(sys.argv[1:])
