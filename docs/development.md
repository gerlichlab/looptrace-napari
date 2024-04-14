## Development
This project uses a Nix shell to provide a development environment. 
To develop on this plugin, please ensure first that you have [installed the Nix package manager](https://nixos.org/download/), ideally, or that you have all the dependencies you'll need otherwise installed (e.g., in a virtual environment you're managing separately).

By default, with `nix-shell`, you should have all the dependencies you'll need not only to _use_ this plugin, but also to _develop_ on it. 
In other words, dependencies to do things like run tests, run linter(s), and run type checking should all be provided. 
If you try and that's not the case, please check the [Issue Tracker](https://github.com/gerlichlab/looptrace-napari/issues).
If an issue's open for what you're experiencing, please upvote the initial description of the issue and/or comment on the ticket.

### Testing, formatting, and linting
Here's what corresponds approximately to what's run for CI through the project's [GitHub actions workflows](../.github/workflows/).

NB: Each of the following commands is to be run _from the project [root folder](../)_.

__Run test suite__ with coverage  statistics
```console
pytest tests -vv --cov=.
```

__Run formatters__
```console
black .
codespell
isort looptrace_napari tests
```

__Run type checker__
```console
mypy looptrace_napari
```

__Run linter__
```console
pylint looptrace_napari
```