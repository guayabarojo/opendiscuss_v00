# Claude Skills Directory

This directory contains reusable patterns and strategies for common development tasks.

## Available Skills

### Parallel Fix Loop (`parallel-fix-loop.md`)

A pattern for efficiently fixing multiple failing tests by spawning parallel agent threads.

**Use when:**
- Multiple tests are failing
- Tests have independent failure causes
- You want to leverage parallel processing for faster fixes

**Key features:**
- Spawns independent agents for each failing test
- Each agent diagnoses, fixes, and verifies the fix
- Supports iterative refinement if some tests remain failing
- Includes resource management and best practices

**Quick reference:**
```bash
# Run this pattern via the command:
/parallel-fix-loop

# Or reference the detailed pattern documentation:
.claude/skills/parallel-fix-loop.md
```

## Usage

Skills in this directory can be:

1. **Referenced** - Use as documentation for implementing patterns manually
2. **Executed** - Some skills have corresponding commands in `.claude/commands/`
3. **Extended** - Copy and adapt patterns for project-specific needs

## Creating New Skills

To add a new skill:

1. Create a markdown file in this directory: `.claude/skills/your-skill-name.md`
2. Document the pattern with:
   - Overview and use cases
   - Step-by-step workflow
   - Example implementations
   - Best practices and variations
3. Optionally create a command file in `.claude/commands/` for easy execution

## Skill vs Command

- **Skills** (this directory): Reusable patterns and strategies documented for reference
- **Commands** (`.claude/commands/`): Executable workflows that can be invoked with `/command-name`

Some skills have both a documentation file (here) and an executable command file.
