<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class InstrumentSet extends Model
{
    use HasFactory;

    protected $fillable = [
        'airport_id',
        'name',
        'relative_path',
        'has_adirs',
        'has_dbright',
        'has_weather',
        'has_strips',
    ];

    protected function casts(): array
    {
        return [
            'has_adirs' => 'boolean',
            'has_dbright' => 'boolean',
            'has_weather' => 'boolean',
            'has_strips' => 'boolean',
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
