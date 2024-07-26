import { Module } from '@nestjs/common';
import { SpotifyController } from './spotify.controller';
import { SpotifyService } from './spotify.service';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Provider } from '../provider.entity';

@Module({
  imports: [TypeOrmModule.forFeature([Provider])],
  controllers: [SpotifyController],
  providers: [SpotifyService],
  exports: [SpotifyService],
})
export class SpotifyModule {}
