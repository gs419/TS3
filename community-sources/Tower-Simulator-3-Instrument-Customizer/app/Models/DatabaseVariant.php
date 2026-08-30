<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class DatabaseVariant extends Model
{
    use HasFactory;

    protected $fillable = [
        'airport_id',
        'name',
        'relative_path',
        'airport_file_relative_path',
        'uses_default_airport_geometry',
    ];

    protected function casts(): array
    {
        return [
            'uses_default_airport_geometry' => 'boolean',
        ];
    }

    public function airport(): BelongsTo
    {
        return $this->belongsTo(Airport::class);
    }

    public function workspaces(): HasMany
    {
        return $this->hasMany(Workspace::class);
    }
}
