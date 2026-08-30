<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Workspace extends Model
{
    use HasFactory;

    protected $fillable = [
        'public_id',
        'user_id',
        'browser_session_id',
        'airport_id',
        'database_variant_id',
        'instrument_set_id',
        'name',
        'status',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function airport(): BelongsTo
    {
        return $this->belongsTo(Airport::class);
    }

    public function databaseVariant(): BelongsTo
    {
        return $this->belongsTo(DatabaseVariant::class);
    }

    public function instrumentSet(): BelongsTo
    {
        return $this->belongsTo(InstrumentSet::class);
    }

    public function screens(): HasMany
    {
        return $this->hasMany(WorkspaceScreen::class);
    }
}
