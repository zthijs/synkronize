import { Module } from '@nestjs/common';
import { SpotifyModule } from './spotify/spotify.module';

@Module({ imports: [SpotifyModule], exports: [SpotifyModule] })
export class ProvidersModule {}
