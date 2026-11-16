# 47 — Running it

**Status: Draft**

Two repositories, one command, one link.

```bash
# in the engine checkout, with the console beside it
git clone https://github.com/drsamonline/tessera-app ../tessera-app
python3 -m tessera.demo
```

```
  API       http://127.0.0.1:8081   token demo-token
  Console   http://127.0.0.1:8080
  Open      http://127.0.0.1:8080/index.html?engine=http://127.0.0.1:8081&token=demo-token
```

## Why this exists

The alternative is: start the API in one terminal, clone the console, serve it with something, read the token out of
the API's output, and paste a URL with two query parameters into a browser. That is five steps, and a demonstration
that takes five steps is abandoned at step three.

`tessera.demo` picks free ports, starts both servers, adds the console's origin to the engine's CORS allowlist, and
prints one link that works.

## What the demo data contains

The seed is deliberately not one record. Six contacts, four companies, four deals, across three simulated systems:

| Situation | Where to look |
|---|---|
| Agreement, two systems say the same thing | Most fields on most contacts |
| Authority — HubSpot owns email, so it wins even when Zendesk disagrees | Asha Rao, Meera Iyer, Priya Nair |
| A field that differs only in case | Daniel Okafor, whose name is capitalised in the support system |
| A record present in one system only | Initech's deal, which NetSuite has never seen |

One contact with one conflict is a unit test. A demo has to show the mesh disagreeing with itself, and it has to do
it inside the canonical schema, a Contact has a name, an email, a phone and a company reference. Stages and amounts
live on Deal, which is why the seed creates three objects rather than inventing fields on one.

## What it is not

- **Not a deployment.** It binds `127.0.0.1`, uses a token printed on stdout, and writes its ledger to a temporary
  directory that disappears with the process.
- **Not the real connectors.** The three nodes are `SimulatedConnector` instances. They speak the canonical contract
  and nothing else. No request leaves the machine.
- **Not authenticated beyond one token.** `demo-token` is `admin`. A demo that ships with a known credential in it is
  a demo that ends up on the internet with a known credential in it, which is why `python3 -m tessera.api` prints a
  generated one instead.
