# GitHub Workflow Guide for macOS

## 1. Verifying SSH Connection

### Check SSH Configuration
```bash
# View SSH config
cat ~/.ssh/config

# List SSH keys
ls -la ~/.ssh/

# Check loaded SSH keys
ssh-add -l

# Test GitHub connection
ssh -T git@github.com
```

### Troubleshooting SSH
```bash
# Verbose connection test
ssh -Tv git@github.com

# Add key to agent if needed
ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# Start SSH agent if needed
eval "$(ssh-agent -s)"
```

## 2. Basic Git Commands

### Repository Setup
```bash
# Clone existing repository
git clone git@github.com:username/repository.git

# Initialize new repository
git init
git remote add origin git@github.com:username/repository.git
```

### Daily Operations
```bash
# Check repository status
git status

# Check current branch
git branch

# View remote repository details
git remote -v
```

## 3. Working with Branches

### Branch Management
```bash
# List all branches (* indicates current branch)
git branch

# Create new branch
git checkout -b feature/new-feature

# Switch to existing branch
git checkout branch-name

# Delete local branch
git branch -d branch-name

# Delete remote branch
git push origin --delete branch-name
```

### Branch Synchronization
```bash
# Update branch list from remote
git fetch origin

# Update current branch with remote changes
git pull origin branch-name

# Push branch to remote
git push origin branch-name
```

## 4. Making Changes

### Staging and Committing
```bash
# Stage specific files
git add filename.ext

# Stage all changes
git add .

# Commit changes
git commit -m "type: brief description"

# Commit types:
# feat:     new feature
# fix:      bug fix
# docs:     documentation changes
# style:    formatting, missing semicolons, etc.
# refactor: code restructuring
# test:     adding tests
# chore:    maintenance tasks
```

### Pushing Changes
```bash
# Push to remote
git push origin branch-name

# Force push (use with caution!)
git push -f origin branch-name
```

## 5. Keeping Repository Updated

### Syncing with Remote
```bash
# Update all remote branches
git fetch --all

# Update specific branch
git pull origin branch-name

# Update and rebase current branch
git pull --rebase origin branch-name
```

## 6. Common Workflows

### Starting New Feature
```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/new-feature

# Make changes, then
git add .
git commit -m "feat: add new feature"
git push origin feature/new-feature
```

### Merging Changes
```bash
# Update target branch
git checkout main
git pull origin main

# Merge feature branch
git merge feature/new-feature

# Push changes
git push origin main
```

### Handling Conflicts
```bash
# If conflicts occur during merge:
1. Open conflicted files
2. Look for conflict markers (<<<<<<, =======, >>>>>>>)
3. Resolve conflicts
4. Stage resolved files
   git add .
5. Complete merge
   git commit -m "merge: resolve conflicts"
```

## 7. Useful Git Configurations

### Setting Up Git Identity
```bash
# Set username
git config --global user.name "Your Name"

# Set email
git config --global user.email "your-email@example.com"

# Set default branch name
git config --global init.defaultBranch main
```

### Helpful Aliases
```bash
# Add aliases
git config --global alias.st "status"
git config --global alias.co "checkout"
git config --global alias.br "branch"
git config --global alias.cm "commit -m"
git config --global alias.unstage "reset HEAD --"

# Using aliases
git st  # instead of git status
git co branch-name  # instead of git checkout branch-name
```

## 8. Best Practices

1. **Branch Naming**
   - `feature/` for new features
   - `fix/` for bug fixes
   - `docs/` for documentation
   - `refactor/` for code restructuring

2. **Commit Messages**
   - Use conventional commits format
   - Start with type: feat, fix, docs, etc.
   - Keep messages clear and concise

3. **Pull Requests**
   - Keep changes focused and small
   - Update branch with main before PR
   - Add clear description of changes

4. **Security**
   - Never commit sensitive data
   - Use .env for secrets
   - Keep .gitignore updated

## 9. Troubleshooting

### Common Issues
```bash
# Reset uncommitted changes
git reset --hard HEAD

# Undo last commit (keeping changes)
git reset --soft HEAD^

# Clean untracked files
git clean -fd

# Check git logs
git log --oneline
```

### SSH Issues
```bash
# Verify SSH key
ssh-add -l

# Add SSH key if missing
ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# Test GitHub connection
ssh -T git@github.com
```
