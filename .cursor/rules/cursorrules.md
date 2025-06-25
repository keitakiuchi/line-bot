# Cursor IDE Rules for LINE Bot カウンセリングアプリケーション

## Code Style Guidelines

### Python
- Use PEP 8 style guide
- Maximum line length: 88 characters (Black formatter)
- Use type hints where appropriate
- Follow snake_case for variables and functions
- Use PascalCase for classes

### File Organization
- Keep related functionality in the same file
- Use descriptive file names
- Group imports: standard library, third-party, local imports

## Development Rules

### Code Quality
- Write clear, readable code with meaningful variable names
- Add docstrings for functions and classes
- Include error handling for external API calls
- Use logging for debugging and monitoring

### Security
- Never commit API keys or sensitive data
- Use environment variables for configuration
- Validate all user inputs
- Implement proper error handling

### Testing
- Write unit tests for critical functions
- Test API endpoints
- Mock external services in tests
- Maintain good test coverage

## Project-Specific Rules

### LINE Bot Integration
- Handle webhook signatures properly
- Implement rate limiting
- Log all interactions for debugging
- Use proper error responses

### AI Integration
- Implement retry logic for API calls
- Cache responses when appropriate
- Monitor API usage and costs
- Handle API failures gracefully

### Database Operations
- Use connection pooling
- Implement proper transaction handling
- Sanitize SQL inputs
- Log database errors

## Git Workflow

### Commit Messages
- Use conventional commit format
- Write descriptive commit messages
- Reference issue numbers when applicable

### Branch Naming
- feature/feature-name
- bugfix/bug-description
- hotfix/urgent-fix

## Documentation

### Code Comments
- Comment complex logic
- Explain business rules
- Document API endpoints
- Keep comments up to date

### README Updates
- Update README when adding new features
- Document environment variables
- Include setup instructions
- Add troubleshooting section

## Performance Guidelines

### Optimization
- Minimize API calls
- Use efficient database queries
- Implement caching where appropriate
- Monitor response times

### Monitoring
- Log performance metrics
- Monitor error rates
- Track API usage
- Set up alerts for critical issues

## Gemini Search

`gemini` is google gemini cli. You can use it for web search.

Run web search via Task Tool with `gemini -p 'WebSearch: ...'`.

```bash
gemini -p "WebSearch: ..."
``` 