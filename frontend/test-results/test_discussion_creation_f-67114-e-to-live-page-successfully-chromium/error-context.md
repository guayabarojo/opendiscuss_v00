# Page snapshot

```yaml
- generic [ref=e4]:
  - generic [ref=e5]: ⚠️
  - heading "Something went wrong" [level=1] [ref=e6]
  - paragraph [ref=e7]: We encountered an unexpected error. This has been logged and our team will investigate.
  - group [ref=e9] [cursor=pointer]:
    - generic "Error Details (for debugging)" [ref=e10]
  - generic [ref=e11]:
    - button "Try Again" [ref=e12] [cursor=pointer]
    - button "Go to Home" [ref=e13] [cursor=pointer]
  - paragraph [ref=e14]:
    - text: If this problem persists, please
    - link "contact support" [ref=e15] [cursor=pointer]:
      - /url: mailto:support@opendiscuss.example
    - text: .
```