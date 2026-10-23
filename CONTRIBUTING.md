# Contributing

Keep changes small and tied to a demonstrated behavior. Open an issue before adding support for another model/build or changing the recovery contract.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_public_tree.py
```

Tests must run without a TV, network, root, proprietary stock files or credentials. Use synthetic stock and emulate only native device, service-manager and security-metadata boundaries. Do not run generated device scripts on the development host.

For new behavior or fixes, retain a causal failing test before changing implementation. Characterization of unchanged inherited behavior can start green; label it honestly. Include ordinary failure, inverse and no-replay checks for state-changing behavior. Never lower a compatibility or preservation guard merely to make an example pass.

Separate offline coverage from actual hardware testing in your report. Give the exact model/build for a voluntary hardware report, but keep device identifiers, network details, account data and raw receipts private. Do not claim zero telemetry, measured performance gains or universal compatibility without evidence.

Contributions to this project's original code and documentation use the MIT license. External dependencies retain their own licenses. Do not contribute Samsung files or copied code without redistribution rights.

AI assistance is welcome, but the human submitting a contribution is responsible for reviewing its code, tests, claims and privacy. Agents should read the staged workflow and recovery documentation before proposing any device operation.
