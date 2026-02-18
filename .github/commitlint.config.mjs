export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature
        'fix',      // Bug fix
        'docs',     // Documentation only
        'style',    // Code style (formatting, etc)
        'refactor', // Code refactoring
        'perf',     // Performance improvement
        'test',     // Adding/updating tests
        'build',    // Build system or dependencies
        'ci',       // CI/CD configuration
        'chore',    // Other changes (maintenance)
        'revert',   // Revert previous commit
      ],
    ],
    'scope-enum': [
      2,
      'always',
      [
        'core',
        'extractors',
        'storage',
        'services',
        'tools',
        'prompts',
        'config',
        'cli',
        'tests',
        'deps',
        'release',
        'no-release', // Prevents release
      ],
    ],
    'scope-case': [2, 'always', 'kebab-case'],
    'subject-case': [2, 'always', 'sentence-case'],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'header-max-length': [2, 'always', 100],
    'body-leading-blank': [2, 'always'],
    'footer-leading-blank': [2, 'always'],
  },
};
