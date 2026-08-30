<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class WorkspaceScreen extends Model
{
    use HasFactory;

    protected $fillable = [
        'workspace_id',
        'screen_type',
        'base_file_name',
        'base_file_hash',
        'changes_json',
        'export_text',
    ];

    protected function casts(): array
    {
        return [
            'changes_json' => 'array',
        ];
    }

    public function workspace(): BelongsTo
    {
        return $this->belongsTo(Workspace::class);
    }
}
