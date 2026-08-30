<?php

namespace App\Http\Controllers;

use App\Models\Workspace;
use App\Models\WorkspaceScreen;
use App\Support\Tower\WorkspaceAdirsService;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

class WorkspaceAdirsController extends Controller
{
    public function edit(int $workspace, WorkspaceAdirsService $service): View
    {
        [$workspace, $screen] = $this->resolveWorkspaceScreen($workspace);

        return view('workspaces/screens/adirs-edit', [
            'workspace' => $workspace,
            'screen' => $screen,
            'payload' => $service->load($workspace, $screen),
        ]);
    }

    public function update(Request $request, int $workspace, WorkspaceAdirsService $service): RedirectResponse
    {
        [$workspace, $screen] = $this->resolveWorkspaceScreen($workspace);

        $validated = $request->validate([
            'changes_json' => ['nullable', 'json'],
        ]);

        $changes = $validated['changes_json'] ?? '{}';
        $decoded = json_decode($changes, true, 512, JSON_THROW_ON_ERROR);
        $screen->update([
            'changes_json' => $service->sanitizeChanges($decoded),
        ]);

        return redirect()
            ->route('workspaces.screens.adirs.edit', $workspace)
            ->with('status', 'ADIRS customization saved.');
    }

    protected function resolveWorkspaceScreen(int $workspaceId): array
    {
        $workspace = auth()->user()
            ->workspaces()
            ->with(['airport', 'databaseVariant', 'instrumentSet', 'screens'])
            ->findOrFail($workspaceId);

        $screen = $workspace->screens()
            ->where('screen_type', 'adirs')
            ->firstOrFail();

        return [$workspace, $screen];
    }
}
