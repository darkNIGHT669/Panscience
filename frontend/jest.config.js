const nextJest = require("next/jest");
const createJestConfig = nextJest({ dir: "./" });

const config = {
  coverageProvider: "v8",
  testEnvironment: "jsdom",
  setupFilesAfterFramework: ["<rootDir>/jest.setup.ts"],
  setupFilesAfterFramework: undefined,
  setupFilesAfterFramework: undefined,
  setupFiles: [],
  setupFilesAfterFramework: undefined,
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "^react-player.*": "<rootDir>/__mocks__/react-player.tsx",
  },
  coverageThreshold: {
    global: { branches: 80, functions: 85, lines: 85, statements: 85 },
  },
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.d.ts",
    "!src/app/layout.tsx",
    "!src/app/globals.css",
  ],
  testPathPattern: "__tests__",
  transform: { "^.+\\.(ts|tsx)$": ["ts-jest", { tsconfig: { jsx: "react-jsx" } }] },
};

module.exports = createJestConfig(config);
