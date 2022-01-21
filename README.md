# downgrade-source

`downgrade-source` is a [pre-commit](https://pre-commit.com/) hook which uses
[lib3to6](https://github.com/mbarkhau/lib3to6) to downgrade your source code into
a separate package.

This allows you to write Py3.6+ code while still allowing it to run under Py3.5, for example.

The generated code will be written to your `<package-directory>/downgraded`, but for this to
work without much effort, you'll need to "redirect" the imports at runtime. See bellow.

## Setting it Up

On your `.pre-commit-config.yaml` add something like:

```yaml
  - repo: https://github.com/s0undt3ch/downgrade-source
    rev: v2.1.0
    hooks:
      - id: downgrade-source
        name: Downgrade source code into a separate package to support Py3.5
        files: ^src/.*\.py$
        exclude: ^src/pytestshellutils/((__init__|version)\.py|downgraded/.*\.py)$
        args:
          - --target-version=3.5
          - --pkg-path=src/pytestshellutils
          - --skip-checker=nounusableimports
          - --skip-checker=nostarimports
```

## Redirect Imports At Runtime

To redirect the imports at runtime, we'll need to add an entry into `sys.meta_path`.

On your `<package-dir>/__init__.py` module, add something like:

```python
import importlib
import sys


USE_DOWNGRADED_CODE = sys.version_info < (3, 6)


if USE_DOWNGRADED_CODE:
    # We generated downgraded code just for Py3.5
    # Let's just import from those modules instead

    PROJECT_PKG_NAME = "<your-project-top-level-package-name>"

    class DowngradedSourceImporter:
        """
        Meta importer to redirect imports on Py35.
        """

        # List of package names which should not be redirected to the
        # downgraded source code.
        NO_REDIRECT_NAMES = (
            "{}.downgraded".format(PROJECT_PKG_NAME),
        )

        def find_module(self, module_name, package_path=None):
            if module_name.startswith(self.NO_REDIRECT_NAMES):
                # The module being imported is on the NO_REDIRECT_NAMES
                # list. Do nothing.
                return None
            if not module_name.startswith(PROJECT_PKG_NAME):
                # The module being imported is not related to our package.
                # Do nothing.
                return None

            # If we reached here, we need to redirect the imports
            return self

        def load_module(self, name):
            # If this is being called, it means we need to redirect the import
            if not name.startswith(self.NO_REDIRECT_NAMES):
                # Redirect the import to the downgraded source
                prefix_length = len(PROJECT_PKG_NAME)
                mod = importlib.import_module(
                    "{}.downgraded.{}".format(
                        PROJECT_PKG_NAME,
                        name[prefix_length:],
                    )
                )
            else:
                # Import without redirection
                mod = importlib.import_module(name)
            sys.modules[name] = mod
            return mod

    # Try our importer first
    sys.meta_path.insert(0, DowngradedSourceImporter())
```

Once this is setup, when the logic matches, the import will be redirected to the downgraded
version of the source code.
