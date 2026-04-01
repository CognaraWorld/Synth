/**
 * TranscribeAI Express application.
 *
 * Wires together the routes and global error-handling middleware.
 * Auth is expected to be handled at the infrastructure level (API gateway,
 * JWT middleware, etc.) before requests reach these routes.
 */

import express, { Request, Response, NextFunction } from "express";
import { AccessDeniedError } from "./auth/accessControl.js";

const app = express();

app.use(express.json());

// Health-check endpoint — no auth required.
app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok" });
});

// Global error handler.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  if (err instanceof AccessDeniedError) {
    return res.status(403).json({ error: err.message });
  }

  // Do not leak internal error details to clients.
  return res.status(500).json({ error: "An unexpected error occurred." });
});

export default app;
