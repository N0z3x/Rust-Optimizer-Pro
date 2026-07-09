# GitHub Pages custom domain setup

Domain:

```text
rustfpsoptimizer.com
```

## DNS records

At your DNS provider / registrar, create these records.

### Apex/root domain

```text
Type: A
Name/Host: @
Value: 185.199.108.153
```

```text
Type: A
Name/Host: @
Value: 185.199.109.153
```

```text
Type: A
Name/Host: @
Value: 185.199.110.153
```

```text
Type: A
Name/Host: @
Value: 185.199.111.153
```

Optional IPv6:

```text
Type: AAAA
Name/Host: @
Value: 2606:50c0:8000::153
```

```text
Type: AAAA
Name/Host: @
Value: 2606:50c0:8001::153
```

```text
Type: AAAA
Name/Host: @
Value: 2606:50c0:8002::153
```

```text
Type: AAAA
Name/Host: @
Value: 2606:50c0:8003::153
```

### www subdomain

```text
Type: CNAME
Name/Host: www
Value: YOUR_GITHUB_USERNAME.github.io
```

Example:

```text
Type: CNAME
Name/Host: www
Value: maksi.github.io
```

## GitHub Pages settings

1. Repository → Settings → Pages.
2. Source: `Deploy from a branch`.
3. Branch: `main`, folder: `/docs`.
4. Custom domain:

```text
rustfpsoptimizer.com
```

5. Save.
6. Wait for DNS check.
7. Enable `Enforce HTTPS` when it becomes available.

## Important

Remove conflicting records:

- old A records for `@`;
- old AAAA records for `@`;
- CNAME for `@` if registrar allowed it;
- parked-domain forwarding records;
- duplicate `www` records that point somewhere else.

DNS propagation can take from a few minutes to 24 hours.
